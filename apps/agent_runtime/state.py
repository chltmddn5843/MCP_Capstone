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
    turn: int  # 모델 호출 횟수
    tool_counts: dict[str, int]  # 도구별 호출 횟수 (같은 도구 3회 제한)
    evidence: list[dict]  # 도구 결과에서 모은 근거
    plan_id: str | None  # create_action_plan 결과
    pending_approval: dict | None  # ApprovalCard
    approval_decision: dict | None  # {approved, reason, by}
    answer: str | None
    started_at: float
    stop_reason: str | None  # answer | turn_limit | time_limit | tool_repeat | rejected | error | ask_user
    intent: str  # recommend | license | update_review | anomaly | general (harness/intent.py)
    conditions: dict[str, bool]  # F2 필수 조건 5개 충족 여부 (recommend일 때만)
