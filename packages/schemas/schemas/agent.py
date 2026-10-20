"""에이전트 런타임 인터페이스. Slack 봇·관리자 화면이 에이전트를 부르는 계약.

평가표의 '상태 저장·재개와 진행 이벤트'를 받치는 부분이다.
  POST /agent/runs                 실행 시작 (thread_id를 주면 이어서)
  GET  /agent/runs/{run_id}        상태·결과 조회 (재개 시 상태 복원 근거)
  GET  /agent/runs/{run_id}/events SSE. 아래 RunEvent를 그대로 흘린다
  POST /agent/runs/{run_id}/resume 승인·추가 입력 뒤 재개
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.common import Evidence, Role, StrEnum


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    waiting_input = "waiting_input"  # 조건 질문 (F2) 등
    waiting_approval = "waiting_approval"  # 조치안 승인 대기
    completed = "completed"
    failed = "failed"


class RunCreate(BaseModel):
    input: str = Field(description="사용자 메시지 또는 프롬프트 인자 설명")
    thread_id: str | None = Field(None, description="있으면 같은 대화를 이어간다")
    prompt_name: str | None = Field(None, description="MCP Prompt 이름. 예: investigate_anomaly")
    prompt_args: dict = {}
    channel: Literal["slack", "admin_ui", "system"] = "slack"


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict
    output: dict | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class RunResult(BaseModel):
    answer: str
    evidence: list[Evidence] = []
    plan_id: str | None = None
    suggested_actions: list[str] = []


class Run(BaseModel):
    run_id: str
    thread_id: str
    status: RunStatus
    requester_id: str
    requester_role: Role
    input: str
    tool_calls: list[ToolCall] = []
    result: RunResult | None = None
    pending_question: str | None = None
    pending_plan_id: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class RunCreated(BaseModel):
    run_id: str
    thread_id: str
    status: RunStatus


class RunResume(BaseModel):
    input: str | None = Field(None, description="waiting_input에 대한 답")
    approved_plan_id: str | None = Field(None, description="waiting_approval 뒤 승인된 plan_id")


class EventType(StrEnum):
    run_started = "run.started"
    message_delta = "message.delta"
    tool_called = "tool.called"
    tool_result = "tool.result"
    input_required = "input.required"
    approval_required = "approval.required"
    run_completed = "run.completed"
    run_failed = "run.failed"


class RunEvent(BaseModel):
    """SSE 한 줄. event=<type>, data=<RunEvent JSON>."""

    type: EventType
    run_id: str
    seq: int
    at: datetime
    text: str | None = None  # message.delta
    tool_call: ToolCall | None = None  # tool.called / tool.result
    question: str | None = None  # input.required
    plan_id: str | None = None  # approval.required
    result: RunResult | None = None  # run.completed
    error: str | None = None  # run.failed
