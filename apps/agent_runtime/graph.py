"""LangGraph StateGraph. 노드·분기·반복은 AGENT_DESIGN.md의 그래프 그림과 같다.

prepare → classify_intent → call_model → check_limits ─┬─ tools ──────────┐
                                      ├─ approval_gate ─┤ (승인 → tools / 거절 → call_model)
                                      └─ finalize → END │
                 ▲────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from apps.agent_runtime.config import MAX_SAME_TOOL, MAX_SECONDS, MAX_TURNS
from apps.agent_runtime.harness.context import fit_context
from apps.agent_runtime.harness.guardrails import approval_summary, is_destructive, public_channel, sanitize_public_answer
from apps.agent_runtime.harness.intents import CLAIM_WORDS, CLASSIFY_PROMPT, PROCEDURE, TOOLS_BY_INTENT, classify_by_keywords, parse_intent
from langchain_core.messages import HumanMessage, SystemMessage
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
        self._bound_cache: dict[str, tuple] = {}

    def bound_for(self, intent: str | None) -> tuple:
        """의도별 도구 부분집합으로 묶은 (model, fallback). 시스템·관리자(의도 없음)는 전체."""
        names = TOOLS_BY_INTENT.get(intent or "")
        if not names or not self.tools:
            return self.model_bound, self.fallback_bound
        key = intent
        if key not in self._bound_cache:
            subset = [t for t in self.tools if t.name in names] or self.tools
            self._bound_cache[key] = (self.model.bind_tools(subset), self.fallback.bind_tools(subset) if self.fallback else None)
        return self._bound_cache[key]


RUNTIMES: dict[str, Runtime] = {}


def _rt(state: AgentState) -> Runtime:
    return RUNTIMES[state["task_id"]]


# ---------- Nodes ----------
async def prepare(state: AgentState) -> dict:
    """작업 단위 카운터를 초기화한다. 대화(messages)는 thread에 남아 이어진다."""
    return {"turn": 0, "tool_counts": {}, "evidence": [], "plan_id": state.get("plan_id"), "plan_created": False, "pending_approval": None,
            "approval_decision": None, "answer": None, "started_at": time.time(), "stop_reason": None, "intent": None}


async def classify_intent(state: AgentState) -> dict:
    """직원 요청의 의도를 분류한다. 시스템 계정이나 prompt_name이 정해진 작업은 분류하지 않는다 (절차가 이미 정해짐)."""
    if state.get("requester_role") == "system" or state.get("prompt_name"):
        return {"intent": "system"}
    rt = _rt(state)
    last = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    text = last.content if last and isinstance(last.content, str) else ""
    try:
        resp, _ = await call_with_recovery(rt.model, rt.fallback, [HumanMessage(content=CLASSIFY_PROMPT.format(text=text))], trace_id=rt.trace_id)
        raw = resp.content if isinstance(resp.content, str) else ""
        intent = parse_intent(raw, text)
    except Exception as exc:  # noqa: BLE001 — 분류 실패는 치명적이지 않다
        record(rt.trace_id, "intent.error", error=str(exc)[:120])
        intent = classify_by_keywords(text)
    record(rt.trace_id, "intent", intent=intent, text=text[:60])
    return {"intent": intent}


def _with_procedure(state: AgentState, msgs: list) -> list:
    """의도별 절차를 system 메시지 끝에 덧붙인다 (원래 system은 thread에 저장된 것)."""
    proc = PROCEDURE.get(state.get("intent") or "", "")
    if not proc or not msgs or not isinstance(msgs[0], SystemMessage):
        return msgs
    return [SystemMessage(content=f"{msgs[0].content}\n\n{proc}")] + list(msgs[1:])


async def call_model(state: AgentState) -> dict:
    rt = _rt(state)
    msgs = _with_procedure(state, fit_context(state["messages"]))
    model, fallback = rt.bound_for(state.get("intent"))
    t0 = time.time()
    ai, used_fallback = await call_with_recovery(model, fallback, msgs, trace_id=rt.trace_id)
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
    plan_created = state.get("plan_created", False)
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
        if isinstance(parsed, dict) and parsed.get("plan_id") and name == "create_action_plan":
            plan_id = parsed["plan_id"]
            plan_created = True
        elif isinstance(parsed, dict) and parsed.get("plan_id"):
            plan_id = parsed["plan_id"]
        ref = next((str(v) for k, v in {**args, **(parsed if isinstance(parsed, dict) else {})}.items() if k.endswith("_id") or k == "url"), name)
        evidence.append({"source": name, "ref": ref, "value": text[:200]})
        out.append(ToolMessage(content=text, tool_call_id=c["id"], name=name))
        record(rt.trace_id, "tool", name=name, error=error, latency_ms=int((time.time() - started) * 1000))
        writer({"type": "TOOL_END", "tool_call": {"id": c["id"], "name": name, "input": args, "output": text[:800], "error": error, "destructive": is_destructive(name)}})
    return {"messages": out, "tool_counts": counts, "evidence": evidence, "plan_id": plan_id, "plan_created": plan_created}


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
    if state.get("intent") in ("access_request", "release_request") and not state.get("plan_created") and CLAIM_WORDS.search(text or ""):
        # Guardrails: 처리 요청을 만들지 않았는데 전달·배정됐다고 말하면 안 된다
        text = CLAIM_WORDS.sub("전달하려면 확인이 필요해", text)
        text += "\n\n아직 관리자에게 전달되지 않았어요. 어떤 제품을 쓰고 싶은지 이름을 알려주시면 바로 전달할게요."
        record(_rt(state).trace_id, "guardrail.claim_without_plan")
    return {"answer": text or "답변을 만들지 못했습니다.", "stop_reason": reason or "answer"}


def build_graph(checkpointer):
    g = StateGraph(AgentState)
    g.add_node("prepare", prepare)
    g.add_node("classify_intent", classify_intent)
    g.add_node("call_model", call_model)
    g.add_node("check_limits", check_limits)
    g.add_node("approval_gate", approval_gate)
    g.add_node("tools", tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "classify_intent")
    g.add_edge("classify_intent", "call_model")
    g.add_edge("call_model", "check_limits")
    g.add_conditional_edges("check_limits", route_after_limits, {"tools": "tools", "approval_gate": "approval_gate", "finalize": "finalize"})
    g.add_conditional_edges("approval_gate", route_after_approval, {"tools": "tools", "call_model": "call_model"})
    g.add_edge("tools", "call_model")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
