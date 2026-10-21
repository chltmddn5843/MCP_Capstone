"""작업 저장소, 진행 이벤트 버스, 그래프 실행기.

- TaskStore: SQLite에 Task JSON을 저장한다 (서버가 재시작돼도 작업 이력과 thread_id가 남는다).
- EventBus: 작업별 이벤트 이력 + 대기자 깨우기. SSE는 이력을 먼저 재생하고 새 이벤트를 기다린다.
- Runner: graph.astream으로 실행하면서 TOKEN·TOOL_START·TOOL_END·APPROVAL_REQUIRED·DONE·FAILED를 발행한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command

from apps.agent_runtime.graph import RUNTIMES, Runtime
from apps.agent_runtime.harness.instructions import build_system_prompt
from apps.agent_runtime.harness.llm import get_models
from apps.agent_runtime.harness.observability import new_trace_id, record
from apps.agent_runtime.harness.tools import load_tools
from schemas.agent import ApprovalCard, EventType, Task, TaskEvent, TaskResult, TaskStatus, ToolCall
from schemas.common import Evidence, Role

log = logging.getLogger("agent.runner")
TOKENS: dict[str, str] = {}  # task_id -> 요청자 토큰. 승인 뒤 재개할 때 같은 역할의 도구를 다시 만들기 위해 메모리에만 둔다.
TERMINAL = {EventType.DONE, EventType.FAILED, EventType.APPROVAL_REQUIRED}


def _now() -> datetime:
    return datetime.now(UTC)


class TaskStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, requester_id TEXT, created_at TEXT, body TEXT)")
        self.conn.commit()

    def save(self, t: Task) -> None:
        self.conn.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?)", (t.task_id, t.requester_id, t.created_at.isoformat(), t.model_dump_json()))
        self.conn.commit()

    @staticmethod
    def _parse(body: str) -> Task | None:
        try:
            return Task.model_validate_json(body)
        except Exception as exc:  # noqa: BLE001  — 스키마가 바뀐 옛 행은 건너뛴다 (예: 역할 축소 전 role=asset)
            log.warning("skip unreadable task row: %s", str(exc)[:120])
            return None

    def get(self, task_id: str) -> Task | None:
        row = self.conn.execute("SELECT body FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._parse(row[0]) if row else None

    def list(self, requester_id: str | None = None, limit: int = 50) -> list[Task]:
        q = "SELECT body FROM tasks" + (" WHERE requester_id=?" if requester_id else "") + " ORDER BY created_at DESC LIMIT ?"
        args = (requester_id, limit) if requester_id else (limit,)
        return [t for t in (self._parse(r[0]) for r in self.conn.execute(q, args)) if t is not None]


class EventBus:
    def __init__(self):
        self.history: dict[str, list[TaskEvent]] = {}
        self.cond: dict[str, asyncio.Condition] = {}

    def _c(self, task_id: str) -> asyncio.Condition:
        return self.cond.setdefault(task_id, asyncio.Condition())

    async def publish(self, task_id: str, type_: EventType, **fields) -> TaskEvent:
        hist = self.history.setdefault(task_id, [])
        ev = TaskEvent(type=type_, task_id=task_id, seq=len(hist) + 1, at=_now(), **fields)
        hist.append(ev)
        c = self._c(task_id)
        async with c:
            c.notify_all()
        return ev

    async def subscribe(self, task_id: str, after: int = 0):
        """after 이후 이벤트를 순서대로 내보내고, 종료 이벤트(DONE·FAILED·APPROVAL_REQUIRED)에서 멈춘다."""
        seq = after
        c = self._c(task_id)
        while True:
            hist = self.history.get(task_id, [])
            while seq < len(hist):
                ev = hist[seq]
                seq += 1
                yield ev
                if ev.type in TERMINAL and seq == len(hist):
                    return
            async with c:
                try:
                    await asyncio.wait_for(c.wait(), timeout=15)
                except TimeoutError:
                    yield None  # keep-alive


class Runner:
    def __init__(self, graph, store: TaskStore, bus: EventBus):
        self.graph, self.store, self.bus = graph, store, bus
        self.model, self.fallback = get_models()

    async def create(self, *, requester_id: str, requester_role: Role, token: str, text: str, thread_id: str | None,
                     prompt_name: str | None, prompt_args: dict, channel: str) -> Task:
        task = Task(task_id=f"task_{uuid.uuid4().hex[:10]}", thread_id=thread_id or f"th_{uuid.uuid4().hex[:10]}", trace_id=new_trace_id(),
                    status=TaskStatus.queued, requester_id=requester_id, requester_role=requester_role, channel=channel, input=text,
                    created_at=_now(), updated_at=_now())
        self.store.save(task)
        TOKENS[task.task_id] = token
        await self._ensure_runtime(task)
        config = {"configurable": {"thread_id": task.thread_id}}
        existing = await self.graph.aget_state(config)
        msgs = [] if (existing.values or {}).get("messages") else [SystemMessage(content=build_system_prompt(requester_role.value, prompt_name, prompt_args, channel))]
        msgs.append(HumanMessage(content=text))
        inputs = {"messages": msgs, "task_id": task.task_id, "requester_id": requester_id, "requester_role": requester_role.value, "prompt_name": prompt_name, "channel": channel}
        asyncio.create_task(self._run(task, inputs, config))
        return task

    async def _ensure_runtime(self, task: Task) -> None:
        if task.task_id in RUNTIMES:
            return
        token = TOKENS.get(task.task_id)
        if token is None:
            raise RuntimeError("서버가 재시작되어 이 작업의 실행 문맥이 없습니다. 같은 thread_id로 새 작업을 만들어 이어가세요.")
        tools = await load_tools(token, task.requester_role)
        RUNTIMES[task.task_id] = Runtime(trace_id=task.trace_id, model=self.model, fallback=self.fallback, tools=tools)

    async def resume(self, task: Task, decision: dict) -> Task:
        await self._ensure_runtime(task)
        task.status = TaskStatus.running
        task.approval = None
        self._save(task)
        config = {"configurable": {"thread_id": task.thread_id}}
        asyncio.create_task(self._run(task, Command(resume=decision), config))
        return task

    async def review_plan(self, plan_id: str, parent: Task) -> None:
        """처리 요청이 승인 대기에 들어가면 시스템 계정으로 review_plan 검토를 돌려 ai_opinion을 붙인다."""
        token = os.getenv("SYSTEM_TOKEN", "dev.sys")
        try:
            await self.create(requester_id="sys", requester_role=Role.system, token=token, text=f"처리 요청 {plan_id}를 검토해 관리자용 의견을 붙여줘",
                              thread_id=None, prompt_name="review_plan", prompt_args={"plan_id": plan_id}, channel="system")
            record(parent.trace_id, "review.spawned", plan_id=plan_id)
        except Exception as exc:  # noqa: BLE001 — 검토 실패는 본 작업에 영향을 주지 않는다
            record(parent.trace_id, "review.error", plan_id=plan_id, error=str(exc)[:160])

    def _save(self, task: Task) -> None:
        task.updated_at = _now()
        self.store.save(task)

    async def _run(self, task: Task, inputs, config) -> None:
        task.status = TaskStatus.running
        self._save(task)
        record(task.trace_id, "task.start", task_id=task.task_id, thread_id=task.thread_id, resume=isinstance(inputs, Command))
        interrupt_card: ApprovalCard | None = None
        try:
            async for mode, chunk in self.graph.astream(inputs, config, stream_mode=["messages", "custom", "updates"]):
                if mode == "messages":
                    msg, meta = chunk
                    if meta.get("langgraph_node") == "call_model":
                        text = msg.content if isinstance(msg.content, str) else "".join(b.get("text", "") for b in msg.content if isinstance(b, dict))
                        if text:
                            await self.bus.publish(task.task_id, EventType.TOKEN, text=text)
                elif mode == "custom":
                    tc = ToolCall(started_at=_now(), **{k: v for k, v in chunk["tool_call"].items()})
                    if chunk["type"] == "TOOL_START":
                        task.tool_calls.append(tc)
                        await self.bus.publish(task.task_id, EventType.TOOL_START, tool_call=tc)
                    else:
                        tc.finished_at = _now()
                        for i, old in enumerate(task.tool_calls):
                            if old.id == tc.id:
                                task.tool_calls[i] = tc
                        await self.bus.publish(task.task_id, EventType.TOOL_END, tool_call=tc)
                    self._save(task)
                elif mode == "updates" and "__interrupt__" in chunk:
                    interrupt_card = ApprovalCard(**chunk["__interrupt__"][0].value)
                    # 스트림을 끝까지 소비해야 interrupt 시점의 checkpoint가 완전히 저장된다. 이벤트는 루프 뒤에 보낸다.
            if interrupt_card is not None:
                task.status, task.approval = TaskStatus.waiting_approval, interrupt_card
                self._save(task)
                await self.bus.publish(task.task_id, EventType.APPROVAL_REQUIRED, approval=interrupt_card)
                record(task.trace_id, "task.waiting_approval", tool=interrupt_card.tool_name)
                return  # 실행 문맥(RUNTIMES)은 재개를 위해 남긴다
            state = await self.graph.aget_state(config)
            v = state.values
            task.turns = v.get("turn", 0)
            task.result = TaskResult(answer=v.get("answer") or "", evidence=[Evidence(**e) for e in v.get("evidence", [])], plan_id=v.get("plan_id"))
            task.status = TaskStatus.done
            self._save(task)
            await self.bus.publish(task.task_id, EventType.DONE, result=task.result)
            record(task.trace_id, "task.done", turns=task.turns, stop_reason=v.get("stop_reason"))
            if v.get("plan_created") and v.get("plan_id") and task.channel != "system":
                asyncio.create_task(self.review_plan(v["plan_id"], parent=task))  # 승인 대기 건에 AI 의견 붙이기 (시스템 계정)
        except Exception as exc:  # noqa: BLE001
            log.exception("task %s failed", task.task_id)
            task.status, task.error = TaskStatus.failed, f"{type(exc).__name__}: {exc}"[:500]
            self._save(task)
            await self.bus.publish(task.task_id, EventType.FAILED, error=task.error)
            record(task.trace_id, "task.failed", error=task.error)
        if task.status in (TaskStatus.done, TaskStatus.failed):
            RUNTIMES.pop(task.task_id, None)
            TOKENS.pop(task.task_id, None)
