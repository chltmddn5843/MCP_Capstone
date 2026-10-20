"""에이전트 런타임 API. schemas/agent.py 계약 그대로.

실행: uv run uvicorn apps.agent_runtime.main:app --reload --port 8002
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, Query
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sse_starlette.sse import EventSourceResponse

from apps.agent_runtime import harness
from apps.agent_runtime.config import CHECKPOINT_DB, TASK_DB
from apps.agent_runtime.graph import build_graph
from apps.agent_runtime.tasks import EventBus, Runner, TaskStore
from apps.backend.errors import ApiError, install_error_handlers, ok
from schemas.agent import ApprovalDecision, Task, TaskCreate, TaskCreated, TaskStatus
from schemas.common import Envelope, ErrorCode, Role
from schemas.entities import Employee

logging.basicConfig(level=logging.INFO, format="%(message)s")
_USER_CACHE: dict[str, tuple[float, Employee]] = {}


async def current_user(authorization: str | None = Header(default=None)) -> Employee:
    """토큰을 백엔드 /me 로 확인한다. 에이전트는 직원 DB를 직접 보지 않는다."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(ErrorCode.unauthorized, "Authorization: Bearer <token> 헤더가 필요합니다")
    token = authorization.split(" ", 1)[1].strip()
    hit = _USER_CACHE.get(token)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    async with harness.tools.backend_client(token) as c:
        r = await c.get("/me")
    body = r.json()
    if "error" in body:
        raise ApiError(ErrorCode(body["error"]["code"]) if body["error"]["code"] in ErrorCode.__members__ else ErrorCode.unauthorized, body["error"]["message"])
    emp = Employee.model_validate(body["data"]["employee"])
    _USER_CACHE[token] = (time.time(), emp)
    return emp


def _token(authorization: str = Header()) -> str:
    return authorization.split(" ", 1)[1].strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(TASK_DB) or ".", exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB) as saver:
        app.state.runner = Runner(build_graph(saver), TaskStore(TASK_DB), EventBus())
        yield


app = FastAPI(title="Agent Runtime", version="0.2.0", lifespan=lifespan)
install_error_handlers(app)


def runner() -> Runner:
    return app.state.runner


@app.post("/ai/tasks", response_model=Envelope[TaskCreated], status_code=202)
async def create_task(body: TaskCreate, user: Employee = Depends(current_user), token: str = Depends(_token)):
    task = await runner().create(requester_id=user.id, requester_role=user.role, token=token, text=body.input, thread_id=body.thread_id,
                                 prompt_name=body.prompt_name, prompt_args=body.prompt_args, channel=body.channel)
    return ok(TaskCreated(task_id=task.task_id, thread_id=task.thread_id, status=task.status))


@app.get("/ai/tasks", response_model=Envelope[list[Task]])
async def list_tasks(mine: bool = True, limit: int = 50, user: Employee = Depends(current_user)):
    if not mine and user.role not in (Role.asset, Role.approver, Role.hrd):
        raise ApiError(ErrorCode.forbidden, "다른 사람의 작업 이력은 관리자만 볼 수 있습니다")
    return ok(runner().store.list(user.id if mine else None, limit))


def _get(task_id: str, user: Employee) -> Task:
    task = runner().store.get(task_id)
    if not task:
        raise ApiError(ErrorCode.not_found, "작업 없음")
    if user.role == Role.employee and task.requester_id != user.id:
        raise ApiError(ErrorCode.forbidden, "본인 작업만 볼 수 있습니다")
    return task


@app.get("/ai/tasks/{task_id}", response_model=Envelope[Task])
async def get_task(task_id: str, user: Employee = Depends(current_user)):
    return ok(_get(task_id, user))


@app.get("/ai/tasks/{task_id}/stream")
async def stream_task(task_id: str, after: int = Query(0, description="이 seq 이후 이벤트부터"), user: Employee = Depends(current_user)):
    _get(task_id, user)

    async def gen():
        async for ev in runner().bus.subscribe(task_id, after):
            if ev is None:
                yield {"comment": "keep-alive"}
            else:
                yield {"event": ev.type.value, "id": str(ev.seq), "data": ev.model_dump_json()}

    return EventSourceResponse(gen())


@app.post("/ai/tasks/{task_id}/approval", response_model=Envelope[TaskCreated], status_code=202)
async def approve_task(task_id: str, body: ApprovalDecision, user: Employee = Depends(current_user)):
    task = _get(task_id, user)
    if task.status != TaskStatus.waiting_approval:
        raise ApiError(ErrorCode.conflict, f"승인 대기 상태가 아님: {task.status.value}")
    if user.role not in (Role.asset, Role.approver, Role.hrd, Role.system):
        raise ApiError(ErrorCode.forbidden, "변경 실행은 자산관리·승인자·HRD만 승인할 수 있습니다")
    try:
        task = await runner().resume(task, {"approved": body.approved, "reason": body.reason, "by": user.id})
    except RuntimeError as exc:
        raise ApiError(ErrorCode.conflict, str(exc))
    return ok(TaskCreated(task_id=task.task_id, thread_id=task.thread_id, status=task.status))
