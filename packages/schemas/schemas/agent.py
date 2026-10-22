"""에이전트 작업 API와 진행 이벤트. Slack 봇·관리자 화면이 에이전트를 부르는 계약.

강의 레퍼런스 아키텍처의 API 계약(표 5-8, 5-9)을 따른다.
  POST /ai/tasks                  질문으로 작업을 만든다 → 202 {task_id}
  GET  /ai/tasks/{id}             상태와 결과 {status, answer, evidence}
  GET  /ai/tasks/{id}/stream      진행 이벤트 (text/event-stream, event=<type>, data=<TaskEvent JSON>)
  POST /ai/tasks/{id}/approval    승인·거절 → 202 (checkpointer에서 그대로 재개)
  GET  /ai/tasks?mine=true        내 작업 이력
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.common import Evidence, Role, StrEnum


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"  # 변경 도구 앞에서 interrupt
    done = "done"
    failed = "failed"


class TaskCreate(BaseModel):
    input: str = Field(description="사용자 질문 또는 요청")
    thread_id: str | None = Field(None, description="있으면 같은 대화(checkpointer thread)를 이어간다")
    prompt_name: str | None = Field(None, description="MCP Prompt 이름. 예: analyze_seat_usage, review_update")
    prompt_args: dict = {}
    channel: Literal["slack", "admin_ui", "system"] = "admin_ui"


class TaskCreated(BaseModel):
    task_id: str
    thread_id: str
    status: TaskStatus


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict
    output: str | None = Field(None, description="길이 제한된 도구 결과")
    error: str | None = None
    destructive: bool = False
    started_at: datetime
    finished_at: datetime | None = None


class ApprovalCard(BaseModel):
    """APPROVAL_REQUIRED 이벤트와 승인 화면이 쓰는 내용."""

    tool_name: str
    tool_input: dict
    plan_id: str | None = None
    summary: str
    risk_level: str | None = None
    evidence: list[Evidence] = []


class TaskResult(BaseModel):
    answer: str
    evidence: list[Evidence] = []
    plan_id: str | None = None
    suggested_actions: list[str] = []


class Task(BaseModel):
    task_id: str
    thread_id: str
    trace_id: str
    status: TaskStatus
    requester_id: str
    requester_role: Role
    channel: str
    input: str
    intent: str | None = None
    feature_route: list[str] = []
    workflow: list[str] = []
    tool_calls: list[ToolCall] = []
    result: TaskResult | None = None
    approval: ApprovalCard | None = None
    error: str | None = None
    turns: int = 0
    created_at: datetime
    updated_at: datetime


class ApprovalDecision(BaseModel):
    approved: bool
    reason: str = Field(min_length=1, description="승인·거절 모두 사유 필수")


class EventType(StrEnum):
    TOKEN = "TOKEN"  # 답변 생성 중 텍스트 조각
    TOOL_START = "TOOL_START"
    TOOL_END = "TOOL_END"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DONE = "DONE"
    FAILED = "FAILED"


class TaskEvent(BaseModel):
    """SSE 한 줄. event=<type>, data=<TaskEvent JSON>."""

    type: EventType
    task_id: str
    seq: int
    at: datetime
    text: str | None = None  # TOKEN
    tool_call: ToolCall | None = None  # TOOL_START / TOOL_END
    approval: ApprovalCard | None = None  # APPROVAL_REQUIRED
    result: TaskResult | None = None  # DONE
    error: str | None = None  # FAILED
