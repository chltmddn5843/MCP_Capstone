"""LangGraph StateGraph. 노드·분기·반복은 AGENT_DESIGN.md의 그래프 그림과 같다.

prepare → classify_intent ─┬─ ask_user → END            (모델 추천인데 F2 조건 부족, 한 번만 묻는다)
                           └─ call_model → check_limits ─┬─ tools ──────────┐
                                                          ├─ approval_gate ─┤ (승인 → tools / 거절 → call_model)
                                                          └─ finalize → END │
                              ▲───────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from apps.agent_runtime.config import MAX_SAME_TOOL, MAX_SECONDS, MAX_TURNS
from apps.agent_runtime.harness.context import fit_context
from apps.agent_runtime.harness import intent as intent_rules
from apps.agent_runtime.harness.guardrails import approval_summary, is_destructive, public_channel, sanitize_public_answer
from apps.agent_runtime.harness.observability import record, usage_of
from apps.agent_runtime.harness.recovery import call_with_recovery
from apps.agent_runtime.harness.tools import shape_result
from apps.agent_runtime.state import AgentState


@dataclass
class Runtime:
    """작업 하나의 실행 문맥. checkpoint에 들어가지 않는 것(모델, 도구 객체)만 둔다."""

    trace_id: str
    model: BaseChatModel
    fallback: BaseChatModel | None
    tools: list[BaseTool]
    tools_by_name: dict[str, BaseTool] = field(init=False)

    def __post_init__(self):
        self.tools_by_name = {t.name: t for t in self.tools}
        self.model_bound = self.model.bind_tools(self.tools) if self.tools else self.model
        self.fallback_bound = self.fallback.bind_tools(self.tools) if (self.fallback and self.tools) else self.fallback


RUNTIMES: dict[str, Runtime] = {}


def _rt(state: AgentState) -> Runtime:
    return RUNTIMES[state["task_id"]]


# ---------- Nodes ----------
async def prepare(state: AgentState) -> dict:
    """작업 단위 카운터를 초기화한다. 대화(messages)는 thread에 남아 이어진다."""
    return {"turn": 0, "tool_counts": {}, "evidence": [], "plan_id": state.get("plan_id"), "pending_approval": None,
            "approval_decision": None, "answer": None, "started_at": time.time(), "stop_reason": None}


async def classify_intent(state: AgentState) -> dict:
    """요청 의도를 정하고, 모델 추천이면 F2 조건 5개가 대화에 나왔는지 본다."""
    msgs = state["messages"]
    text = str(next((m.content for m in reversed(msgs) if isinstance(m, HumanMessage)), ""))
    found = intent_rules.classify(text, state.get("prompt_name"))
    record(_rt(state).trace_id, "intent", intent=found)
    if found != "recommend":
        return {"intent": found, "conditions": {}}
    return {"intent": found, "conditions": intent_rules.conditions([str(m.content) for m in msgs if isinstance(m, HumanMessage)])}


def route_after_intent(state: AgentState) -> str:
    if state.get("intent") != "recommend" or state.get("channel") == "system" or all(state.get("conditions", {}).values()):
        return "call_model"
    prev_ai = next((m for m in reversed(state["messages"][:-1]) if isinstance(m, AIMessage)), None)
    if prev_ai is not None and prev_ai.additional_kwargs.get("ask_user"):
        return "call_model"  # 이미 한 번 물었다. 같은 질문을 반복하지 않고 있는 정보로 진행한다
    return "ask_user"


async def ask_user(state: AgentState) -> dict:
    """부족한 조건을 질문 하나로 묶어 답으로 돌려주고 끝낸다. 직원이 답하면 같은 thread로 이어진다."""
    q = intent_rules.question([k for k, ok in state.get("conditions", {}).items() if not ok])
    return {"messages": [AIMessage(content=q, additional_kwargs={"ask_user": True})], "answer": q, "stop_reason": "ask_user"}


async def call_model(state: AgentState) -> dict:
    rt = _rt(state)
    msgs = fit_context(state["messages"])
    t0 = time.time()
    ai, used_fallback = await call_with_recovery(rt.model_bound, rt.fallback_bound, msgs, trace_id=rt.trace_id)
    record(rt.trace_id, "llm", node="call_model", turn=state.get("turn", 0) + 1, latency_ms=int((time.time() - t0) * 1000),
           tool_calls=[c["name"] for c in ai.tool_calls], fallback=used_fallback, **usage_of(ai))
    return {"messages": [ai], "turn": state.get("turn", 0) + 1}


async def check_limits(state: AgentState) -> dict:
    """Agent Loop 한도: 턴, 시간, 같은 도구 반복."""
    ai = state["messages"][-1]
    if not isinstance(ai, AIMessage) or not ai.tool_calls:
        return {}
    if state.get("turn", 0) >= MAX_TURNS:
        return {"stop_reason": "turn_limit"}
    if time.time() - state.get("started_at", time.time()) > MAX_SECONDS:
        return {"stop_reason": "time_limit"}
    counts = state.get("tool_counts", {})
    for c in ai.tool_calls:
        if counts.get(c["name"], 0) >= MAX_SAME_TOOL:
            return {"stop_reason": "tool_repeat"}
    return {}


def route_after_limits(state: AgentState) -> str:
    ai = state["messages"][-1]
    if state.get("stop_reason") in ("turn_limit", "time_limit", "tool_repeat"):
        return "finalize"
    if not isinstance(ai, AIMessage) or not ai.tool_calls:
        return "finalize"
    exposed = _rt(state).tools_by_name
    if any(is_destructive(c["name"]) and c["name"] in exposed for c in ai.tool_calls):
        return "approval_gate"  # 역할에 노출되지 않은 도구는 tools 노드가 not_found로 돌려준다
    return "tools"


async def approval_gate(state: AgentState) -> dict:
    """변경 도구 앞에서 멈춘다. interrupt 값이 승인 카드이고, 재개 값이 결정이다."""
    ai = state["messages"][-1]
    tc = next(c for c in ai.tool_calls if is_destructive(c["name"]))
    card = {"tool_name": tc["name"], "tool_input": tc["args"], "plan_id": tc["args"].get("plan_id") or state.get("plan_id"),
            "summary": approval_summary(tc["name"], tc["args"]), "evidence": state.get("evidence", [])[-5:]}
    decision = interrupt(card)  # 재개 전까지 여기서 멈춘다 (checkpointer에 저장)
    rt = _rt(state)
    record(rt.trace_id, "approval", tool=tc["name"], approved=decision.get("approved"), by=decision.get("by"))
    if decision.get("approved"):
        return {"pending_approval": None, "approval_decision": decision}
    rejected = [ToolMessage(content=json.dumps({"error": {"code": "rejected", "message": f"승인자가 거절했습니다: {decision.get('reason', '')}"}}, ensure_ascii=False),
                            tool_call_id=c["id"], name=c["name"]) for c in ai.tool_calls]
    return {"messages": rejected, "pending_approval": None, "approval_decision": decision, "stop_reason": "rejected"}


def route_after_approval(state: AgentState) -> str:
    return "tools" if (state.get("approval_decision") or {}).get("approved") else "call_model"


async def tools(state: AgentState) -> dict:
    rt = _rt(state)
    writer = get_stream_writer()
    ai = state["messages"][-1]
    counts = dict(state.get("tool_counts", {}))
    evidence = list(state.get("evidence", []))
    plan_id = state.get("plan_id")
    out: list[ToolMessage] = []
    for c in ai.tool_calls:
        name, args = c["name"], c["args"]
        started = time.time()
        writer({"type": "TOOL_START", "tool_call": {"id": c["id"], "name": name, "input": args, "destructive": is_destructive(name)}})
        tool = rt.tools_by_name.get(name)
        error = None
        if tool is None:
            text = json.dumps({"error": {"code": "not_found", "message": f"도구 {name} 은(는) 이 역할에 노출되지 않습니다"}}, ensure_ascii=False)
            error = "not_found"
        else:
            try:
                text = shape_result(await tool.ainvoke(args))
            except Exception as exc:  # noqa: BLE001  — 오류는 ToolMessage로 모델에 돌려준다
                text = json.dumps({"error": {"code": "tool_error", "message": str(exc)[:500]}}, ensure_ascii=False)
                error = str(exc)[:200]
        if error is None and text.lstrip().startswith('{"error"'):
            error = text[:200]
        counts[name] = counts.get(name, 0) + 1
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            parsed = None
        if isinstance(parsed, dict) and parsed.get("plan_id"):
            plan_id = parsed["plan_id"]
        ref = next((str(v) for k, v in {**args, **(parsed if isinstance(parsed, dict) else {})}.items() if k.endswith("_id") or k == "url"), name)
        evidence.append({"source": name, "ref": ref, "value": text[:200]})
        out.append(ToolMessage(content=text, tool_call_id=c["id"], name=name))
        record(rt.trace_id, "tool", name=name, error=error, latency_ms=int((time.time() - started) * 1000))
        writer({"type": "TOOL_END", "tool_call": {"id": c["id"], "name": name, "input": args, "output": text[:800], "error": error, "destructive": is_destructive(name)}})
    return {"messages": out, "tool_counts": counts, "evidence": evidence, "plan_id": plan_id}


async def finalize(state: AgentState) -> dict:
    ai = state["messages"][-1]
    text = ""
    if isinstance(ai, AIMessage):
        text = ai.content if isinstance(ai.content, str) else "".join(b.get("text", "") for b in ai.content if isinstance(b, dict))
    reason = state.get("stop_reason")
    if reason in ("turn_limit", "time_limit", "tool_repeat"):
        label = {"turn_limit": "최대 턴 수", "time_limit": "작업 시간 한도", "tool_repeat": "같은 도구 반복 한도"}[reason]
        text = (text + "\n\n" if text else "") + f"({label}에 도달해 여기까지 확인한 내용으로 답합니다. 추가 확인이 필요하면 다시 요청해 주세요.)"
    if public_channel(state.get("requester_role"), state.get("channel")):  # Guardrails: 직원·Slack에는 자연어만
        text = sanitize_public_answer(text)
    return {"answer": text or "답변을 만들지 못했습니다.", "stop_reason": reason or "answer"}


def build_graph(checkpointer):
    g = StateGraph(AgentState)
    g.add_node("prepare", prepare)
    g.add_node("classify_intent", classify_intent)
    g.add_node("ask_user", ask_user)
    g.add_node("call_model", call_model)
    g.add_node("check_limits", check_limits)
    g.add_node("approval_gate", approval_gate)
    g.add_node("tools", tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "classify_intent")
    g.add_conditional_edges("classify_intent", route_after_intent, {"call_model": "call_model", "ask_user": "ask_user"})
    g.add_edge("ask_user", END)
    g.add_edge("call_model", "check_limits")
    g.add_conditional_edges("check_limits", route_after_limits, {"tools": "tools", "approval_gate": "approval_gate", "finalize": "finalize"})
    g.add_conditional_edges("approval_gate", route_after_approval, {"tools": "tools", "call_model": "call_model"})
    g.add_edge("tools", "call_model")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
