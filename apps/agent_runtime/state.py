"""그래프 State. AGENT_DESIGN.md의 State 표와 같다."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    task_id: str
    requester_id: str
    requester_role: str
    prompt_name: str | None
    channel: str  # slack | admin_ui | system. slack이면 답변을 자연어로만 (내부 식별자 비노출)
    intent: str  # classify_intent 결과. access_request | release_request | recommendation | policy_question | status_or_other | system
    plan_created: bool  # 이번 작업에서 처리 요청을 만들었는가 (완료 선언 검사용)
    turn: int  # 모델 호출 횟수
    tool_counts: dict[str, int]  # 도구별 호출 횟수 (같은 도구 3회 제한)
    evidence: list[dict]  # 도구 결과에서 모은 근거
    plan_id: str | None  # create_action_plan 결과
    pending_approval: dict | None  # ApprovalCard
    approval_decision: dict | None  # {approved, reason, by}
    answer: str | None
    started_at: float
    stop_reason: str | None  # answer | turn_limit | time_limit | tool_repeat | rejected | error
