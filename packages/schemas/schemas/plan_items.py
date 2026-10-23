"""action_plans.items 원소의 type별 형태. 백엔드는 create 시 이 모델로 검증하고,
에이전트는 이 모양으로 items를 만들고, 승인함 UI는 이걸로 표시한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import Environment, PlanType


class SeatAssignItem(BaseModel):
    employee_id: str
    contract_id: str


class SeatReclaimItem(BaseModel):
    employee_id: str
    contract_id: str
    confirmation_id: str | None = Field(None, description="본인 확인 응답 id. 무응답이면 회수하지 않는다")
    reassign_to_employee_id: str | None = None


class ApiAccessItem(BaseModel):
    """사용량 과금 제품(API)의 사용 신청. 승인되면 백엔드가 프로젝트를 만든다."""

    tool_id: str
    purpose: str = Field(description="업무 목적. 예: 세일즈 데이터 자동 분석")
    model_id: str | None = None
    expected_requests_per_day: int | None = None
    environment: Environment = Environment.test


class ModelChangeItem(BaseModel):
    project_id: str
    from_model_id: str
    to_model_id: str
    environment: Environment = Environment.test  # prod면 risk_level=high


class BudgetReviewItem(BaseModel):
    project_id: str
    current_budget_krw: int
    proposed_budget_krw: int | None = None
    note: str | None = None


class PurchaseReviewItem(BaseModel):
    tool_id: str | None = None
    contract_id: str | None = None
    quantity: int | None = None
    note: str | None = None
    product_name: str | None = Field(None, description="사내 등록 제품 목록에 없는 제품 이름 (미도입 신청, PRD S9)")
    purpose: str | None = Field(None, description="신청 용도")


PLAN_ITEM_MODELS: dict[PlanType, type[BaseModel]] = {
    PlanType.seat_assign: SeatAssignItem,
    PlanType.seat_reclaim: SeatReclaimItem,
    PlanType.api_access: ApiAccessItem,
    PlanType.model_change: ModelChangeItem,
    PlanType.budget_review: BudgetReviewItem,
    PlanType.purchase_review: PurchaseReviewItem,
}


def validate_items(plan_type: PlanType, items: list[dict]) -> list[dict]:
    """type에 맞는 모델로 검증해 정규화한 dict 목록을 돌려준다. 틀리면 pydantic.ValidationError."""
    model = PLAN_ITEM_MODELS[plan_type]
    return [model.model_validate(i).model_dump() for i in items]
