"""에이전트 런타임 스텁. Slack 봇·관리자 화면이 붙을 인터페이스만 고정 응답으로 제공한다.
실제 도구 호출 루프는 C(에이전트) 담당이 이 라우트를 유지한 채 채운다.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI
from sse_starlette.sse import EventSourceResponse

from apps.backend.auth import current_user
from apps.backend.errors import ApiError, install_error_handlers, ok
from schemas.agent import (
    EventType,
    Run,
    RunCreate,
    RunCreated,
    RunEvent,
    RunResult,
    RunResume,
    RunStatus,
    ToolCall,
)
from schemas.common import Envelope, ErrorCode, Evidence
from schemas.entities import Employee

app = FastAPI(title="Agent Runtime", version="0.1.0")
install_error_handlers(app)
RUNS: dict[str, Run] = {}


def _now():
    return datetime.now(UTC)


@app.post("/agent/runs", response_model=Envelope[RunCreated], status_code=202)
def create_run(body: RunCreate, user: Employee = Depends(current_user)):
    run_id, thread_id = uuid.uuid4().hex[:12], body.thread_id or uuid.uuid4().hex[:12]
    RUNS[run_id] = Run(run_id=run_id, thread_id=thread_id, status=RunStatus.running, requester_id=user.id, requester_role=user.role, input=body.input, created_at=_now(), updated_at=_now())
    return ok(RunCreated(run_id=run_id, thread_id=thread_id, status=RunStatus.running))


@app.get("/agent/runs/{run_id}", response_model=Envelope[Run])
def get_run(run_id: str, user: Employee = Depends(current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise ApiError(ErrorCode.not_found, "run 없음")
    return ok(run)


@app.post("/agent/runs/{run_id}/resume", response_model=Envelope[RunCreated], status_code=202)
def resume_run(run_id: str, body: RunResume, user: Employee = Depends(current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise ApiError(ErrorCode.not_found, "run 없음")
    if run.status not in (RunStatus.waiting_input, RunStatus.waiting_approval):
        raise ApiError(ErrorCode.conflict, f"재개할 수 없는 상태: {run.status.value}")
    RUNS[run_id] = run.model_copy(update={"status": RunStatus.running, "updated_at": _now()})
    return ok(RunCreated(run_id=run_id, thread_id=run.thread_id, status=RunStatus.running))


@app.get("/agent/runs/{run_id}/events")
async def events(run_id: str, user: Employee = Depends(current_user)):
    run = RUNS.get(run_id)
    if not run:
        raise ApiError(ErrorCode.not_found, "run 없음")

    async def gen():
        tc = ToolCall(id="tc_1", name="get_my_profile", input={}, started_at=_now())
        result = RunResult(answer="(스텁) 등록 업무를 확인했습니다.", evidence=[Evidence(source="me", ref=run.requester_id)])
        seq = [
            RunEvent(type=EventType.run_started, run_id=run_id, seq=1, at=_now()),
            RunEvent(type=EventType.tool_called, run_id=run_id, seq=2, at=_now(), tool_call=tc),
            RunEvent(type=EventType.tool_result, run_id=run_id, seq=3, at=_now(), tool_call=tc.model_copy(update={"output": {"ok": True}, "finished_at": _now()})),
            RunEvent(type=EventType.message_delta, run_id=run_id, seq=4, at=_now(), text="등록 업무를 확인했습니다."),
            RunEvent(type=EventType.run_completed, run_id=run_id, seq=5, at=_now(), result=result),
        ]
        for ev in seq:
            await asyncio.sleep(0.2)
            yield {"event": ev.type.value, "data": ev.model_dump_json()}
        RUNS[run_id] = run.model_copy(update={"status": RunStatus.completed, "result": result, "tool_calls": [tc], "updated_at": _now()})

    return EventSourceResponse(gen())
