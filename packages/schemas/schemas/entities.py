"""6절 데이터 모델의 응답 형태. REST와 MCP 도구 출력이 공유한다."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from schemas.common import (
    AnomalyStatus,
    Base,
    BillingType,
    ConfirmationAnswer,
    DataClass,
    EmployeeStatus,
    Environment,
    Evidence,
    LicenseFlag,
    Money,
    PlanStatus,
    PlanType,
    Reaction,
    RiskLevel,
    Role,
    SavingsKind,
    SeatStatus,
    SourceKind,
    SuggestionStatus,
    TargetType,
    TaskSource,
    ToolApprovalStatus,
    UnmetNeedStatus,
)


class Department(Base):
    id: str
    name: str
    parent_id: str | None = None


class Employee(Base):
    id: str
    name: str
    email: str
    dept_id: str
    dept_name: str | None = None
    role: Role
    job_title: str
    status: EmployeeStatus = EmployeeStatus.active
    hire_date: datetime | None = None
    slack_user_id: str | None = None


class Tool(Base):
    id: str
    vendor: str
    product: str
    category: str
    approval_status: ToolApprovalStatus
    allowed_data_class: DataClass
    policy_note: str | None = None


class Contract(Base):
    id: str
    tool_id: str
    plan_name: str
    billing_type: BillingType
    seats_purchased: int
    seat_price_krw: int
    term_start: datetime
    term_end: datetime
    mid_term_reduction: bool = False


class ToolWithPlan(Tool):
    """list_approved_tools 출력: 도구 + 현재 계약 플랜 요약."""

    contract: Contract | None = None


class Model(Base):
    id: str
    vendor: str
    name: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    approved: bool = True
    allowed_data_class: DataClass


class RegisteredTask(Base):
    id: str
    employee_id: str
    title: str
    description: str
    frequency: str = Field(description="예: daily, weekly, monthly, adhoc")
    tools_used: list[str] = []
    source: TaskSource = TaskSource.manual
    updated_at: datetime


class VendorSource(Base):
    id: str
    vendor: str
    url: str
    kind: SourceKind
    is_candidate: bool = False


class VendorUpdate(Base):
    id: str
    source_id: str
    vendor: str
    published_at: datetime
    title: str
    summary: str
    url: str = Field(description="원문 링크. 필수")
    affected_plans: list[str] = []
    fetched_at: datetime


class Suggestion(Base):
    id: str
    update_id: str
    target_type: TargetType
    target_id: str | None = None
    task_id: str | None = None
    relevance: str = Field(description="관련성 근거 한 줄")
    body: str
    status: SuggestionStatus
    hold_reason: str | None = Field(None, description="보류 사유. 예: 회사 플랜에 없는 기능, 관련 업무 근거 없음")
    sent_at: datetime | None = None


class Feedback(Base):
    id: str
    suggestion_id: str
    employee_id: str
    reaction: Reaction
    created_at: datetime


class EvalResult(Base):
    id: str
    task_type: str
    model_id: str
    quality_score: float
    threshold: float
    passed: bool
    avg_input_tokens: int
    avg_output_tokens: int
    latency_ms: int
    evaluated_at: datetime


class UnmetNeed(Base):
    id: str
    employee_id: str
    dept_id: str
    summary: str
    capability_tag: str
    status: UnmetNeedStatus = UnmetNeedStatus.open
    created_at: datetime


class Project(Base):
    id: str
    name: str
    dept_id: str
    owner_id: str
    purpose: str
    model_id: str
    environment: Environment
    monthly_budget_krw: int


class SeatAssignment(Base):
    id: str
    contract_id: str
    employee_id: str
    assigned_at: datetime
    unassigned_at: datetime | None = None
    status: SeatStatus
    last_activity_at: datetime | None = None
    flag: LicenseFlag | None = None


class UsageSummary(Base):
    scope: str
    scope_id: str
    period_start: datetime
    period_end: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    cost: Money
    last_activity_at: datetime | None = None


class UsagePoint(Base):
    period_start: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    cost: Money


class BreakdownRow(Base):
    key: str = Field(description="model명, api_key id, 또는 입력 길이 구간(예: 0-1k)")
    requests: int
    input_tokens: int
    output_tokens: int
    cost: Money
    share: float = Field(description="전체 대비 비율 0~1")


class Anomaly(Base):
    id: str
    scope_type: str
    scope_id: str
    scope_name: str | None = None
    rule: str = Field(description="예: daily_cost_gt_3x_baseline")
    baseline: float
    observed: float
    ratio: float
    projected_monthly_cost: Money | None = None
    status: AnomalyStatus
    created_at: datetime


class ActionPlan(Base):
    id: str
    type: PlanType
    risk_level: RiskLevel
    status: PlanStatus
    items: list[dict] = Field(description="type별 실행 항목. 예: [{employee_id, contract_id}]")
    rationale: str
    evidence: list[Evidence] = []
    requested_by: str
    approver_id: str | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    result: dict | None = None
    reject_reason: str | None = None
    created_at: datetime


class Confirmation(Base):
    id: str
    plan_id: str
    employee_id: str
    question: str
    answer: ConfirmationAnswer | None = None
    due_at: datetime
    answered_at: datetime | None = None


class SavingsEntry(Base):
    id: str
    plan_id: str
    kind: SavingsKind
    amount_krw: int
    basis: str


class AuditEntry(Base):
    id: str
    actor_id: str
    actor_role: Role
    action: str
    target: str
    before: dict | None = None
    after: dict | None = None
    created_at: datetime
