"""8절 백엔드 REST API 요청·응답 모델.

경로별 매핑은 파일 끝의 ROUTES 표를 본다. 백엔드는 이 모델로 response_model을 걸고,
MCP 서버·UI·Slack은 이 모델로 응답을 파싱한다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import (
    BreakdownBy,
    ConfirmationAnswer,
    Evidence,
    Granularity,
    LicenseFlag,
    Money,
    PlanStatus,
    PlanType,
    Reaction,
    RiskLevel,
    Role,
    SavingsKind,
    SuggestionStatus,
    TargetType,
    TaskSource,
    UsageScope,
)
from schemas.entities import (
    ActionPlan,
    Anomaly,
    AuditEntry,
    BreakdownRow,
    Confirmation,
    Contract,
    Employee,
    EvalResult,
    Model,
    Project,
    RegisteredTask,
    Suggestion,
    ToolWithPlan,
    UnmetNeed,
    UsagePoint,
    UsageSummary,
    VendorUpdate,
)


# ---------- /auth ----------
class DevLoginRequest(BaseModel):
    employee_id: str


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee: Employee


# ---------- /me ----------
class MeResponse(BaseModel):
    employee: Employee
    tasks: list[RegisteredTask]
    available_tools: list[ToolWithPlan]


class TaskCreate(BaseModel):
    title: str
    description: str
    frequency: str
    tools_used: list[str] = []
    source: TaskSource = TaskSource.manual


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    frequency: str | None = None
    tools_used: list[str] | None = None


# ---------- /updates ----------
class RelevantTaskCandidate(BaseModel):
    """HRD에게는 employee_id 없이 팀 단위(team_id, job_title)로만 내려간다."""

    task_id: str
    job_title: str
    team_id: str
    employee_id: str | None = None
    summary: str


class RelevantTasksResponse(BaseModel):
    update: VendorUpdate
    candidates: list[RelevantTaskCandidate]


# ---------- /suggestions ----------
class SuggestionCreate(BaseModel):
    update_id: str
    target_type: TargetType
    target_id: str | None = None
    task_id: str | None = None
    relevance: str
    body: str


class FeedbackCreate(BaseModel):
    reaction: Reaction


class SuggestionListQuery(BaseModel):
    status: SuggestionStatus | None = None
    update_id: str | None = None


# ---------- /adoption ----------
class TeamAdoption(BaseModel):
    team_id: str
    team_name: str
    headcount: int = Field(description="5명 미만 팀은 목록에서 제외")
    suggestions_sent: int
    useful: int
    irrelevant: int
    questions: int
    active_ratio: float = Field(description="활동 인원 비율 0~1")
    top_questions: list[str] = []


# ---------- /eval-results, /estimates ----------
class TaskCostEstimateRequest(BaseModel):
    model_id: str
    requests_per_day: int
    avg_input_tokens: int
    avg_output_tokens: int
    working_days_per_month: int = 22


class TaskCostEstimateResponse(BaseModel):
    model: Model
    daily: Money
    monthly: Money
    fx_rate_krw_per_usd: float
    formula: str = Field(description="사람이 읽는 계산식")


# ---------- /unmet-needs ----------
class UnmetNeedCreate(BaseModel):
    summary: str
    capability_tag: str


class UnmetNeedCreateResponse(BaseModel):
    need: UnmetNeed
    same_tag_count: int
    same_tag_dept_count: int
    threshold_met: bool


class UnmetNeedAggregate(BaseModel):
    capability_tag: str
    count: int
    dept_count: int
    threshold_met: bool
    sample_summaries: list[str] = []


# ---------- /inventory ----------
class LowUsageCandidate(BaseModel):
    employee_id: str
    employee_name: str
    dept_name: str
    last_activity_at: datetime | None
    flag: LicenseFlag
    needs_confirmation: bool


class ContractInventory(BaseModel):
    contract: Contract
    tool_name: str
    purchased: int
    assigned: int
    unassigned: int
    low_usage_candidates: list[LowUsageCandidate]


# ---------- /usage ----------
class UsageQuery(BaseModel):
    scope: UsageScope
    scope_id: str
    start: datetime
    end: datetime
    granularity: Granularity = Granularity.day
    group_by: BreakdownBy | None = None


class UsageResponse(BaseModel):
    summary: UsageSummary
    series: list[UsagePoint] = []
    breakdown: list[BreakdownRow] = []


# ---------- /anomalies ----------
class AnomalyDetail(BaseModel):
    anomaly: Anomaly
    project: Project | None = None
    series: list[UsagePoint]
    breakdown_by_model: list[BreakdownRow] = []
    breakdown_by_input_length: list[BreakdownRow] = []


# ---------- /plans ----------
class PlanCreate(BaseModel):
    type: PlanType
    items: list[dict]
    rationale: str
    evidence: list[Evidence]


class PlanListQuery(BaseModel):
    status: PlanStatus | None = None
    type: PlanType | None = None


class PlanDecision(BaseModel):
    reason: str = Field(min_length=1, description="승인·반려 모두 사유 필수")


class PlanExecuteResponse(BaseModel):
    plan: ActionPlan
    result: dict
    verified: dict = Field(description="실행 후 재조회 결과")
    savings: list[dict] = []


# ---------- /confirmations ----------
class ConfirmationCreate(BaseModel):
    """저사용 이용권 소유자에게 사용 의사를 묻는다. 응답 기한은 서버가 5영업일로 정한다 (9절 알림 정책)."""

    employee_id: str
    plan_id: str
    question: str


class ConfirmationAnswerRequest(BaseModel):
    answer: ConfirmationAnswer


# ---------- /savings ----------
class SavingsSummary(BaseModel):
    by_kind: dict[SavingsKind, int]
    total_krw: int


# ---------- /internal/jobs ----------
class JobRunResponse(BaseModel):
    job: str
    started_at: datetime
    finished_at: datetime
    result: dict


# ---------- 경로 표 (문서용, 백엔드 라우터와 일치해야 함) ----------
ROUTES: list[tuple[str, str, str, list[Role]]] = [
    ("POST", "/auth/dev-login", "시드 직원으로 토큰 발급", []),
    ("GET", "/me", "본인 프로필·업무·이용 가능 도구", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/me/tasks", "본인 등록 업무", [Role.employee]),
    ("POST", "/me/tasks", "업무 등록", [Role.employee]),
    ("PATCH", "/me/tasks/{task_id}", "업무 수정", [Role.employee]),
    ("GET", "/tools", "승인 도구·플랜", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/models", "승인 모델·단가", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/updates", "수집된 업데이트", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/updates/{update_id}", "업데이트 상세", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/updates/{update_id}/relevant-tasks", "관련 업무 후보", [Role.system, Role.hrd]),
    ("GET", "/suggestions", "제안 목록", [Role.system, Role.hrd]),
    ("POST", "/suggestions", "제안 저장", [Role.system, Role.hrd]),
    ("POST", "/suggestions/{suggestion_id}/approve", "공지 승인 후 발송", [Role.hrd]),
    ("POST", "/suggestions/{suggestion_id}/feedback", "피드백", [Role.employee, Role.hrd, Role.asset, Role.approver]),
    ("GET", "/adoption/teams", "팀 단위 활용 지표", [Role.hrd]),
    ("GET", "/eval-results", "모델 평가 결과", [Role.employee, Role.asset, Role.system]),
    ("POST", "/estimates/task-cost", "예상 비용 계산", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("GET", "/unmet-needs", "미충족 수요 집계", [Role.hrd, Role.asset, Role.approver]),
    ("POST", "/unmet-needs", "미충족 수요 기록", [Role.employee, Role.hrd, Role.asset]),
    ("GET", "/inventory", "이용권 현황", [Role.asset, Role.approver, Role.system]),
    ("GET", "/usage", "사용량", [Role.employee, Role.asset, Role.system]),
    ("GET", "/anomalies", "경보 목록", [Role.asset, Role.system]),
    ("GET", "/anomalies/{anomaly_id}", "경보 상세", [Role.asset, Role.system]),
    ("GET", "/plans", "조치안 목록", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("POST", "/plans", "조치안 생성. 직원: seat_assign(본인)·model_change(본인 소유 프로젝트, test). HRD: notice_send", [Role.employee, Role.hrd, Role.asset, Role.system]),
    ("GET", "/plans/{plan_id}", "조치안 상태", [Role.employee, Role.hrd, Role.asset, Role.approver, Role.system]),
    ("POST", "/plans/{plan_id}/approve", "승인", [Role.hrd, Role.asset, Role.approver]),
    ("POST", "/plans/{plan_id}/reject", "반려", [Role.hrd, Role.asset, Role.approver]),
    ("POST", "/plans/{plan_id}/execute", "실행 (Idempotency-Key 필수)", [Role.asset, Role.system]),
    ("POST", "/confirmations", "사용 의사 확인 요청 생성 (due_at = 5영업일)", [Role.asset, Role.system]),
    ("POST", "/confirmations/{confirmation_id}/answer", "사용 의사 응답", [Role.employee]),
    ("GET", "/savings", "절감 합계", [Role.asset, Role.approver]),
    ("GET", "/audit-log", "감사 기록", [Role.asset, Role.approver]),
    ("POST", "/internal/jobs/{job_name}/run", "배치 수동 실행", [Role.system, Role.asset]),
]
