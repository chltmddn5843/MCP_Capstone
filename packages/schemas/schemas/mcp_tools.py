"""7절 MCP 도구 명세. 입력·출력 모델과 역할별 노출, 힌트를 한 곳에 둔다.

MCP 서버는 TOOLS를 순회하며 FastMCP에 등록하고, 요청자 역할이 roles에 없으면
tools/list에서 숨긴다. 에이전트는 같은 모델로 출력을 파싱한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import (
    AnomalyStatus,
    BreakdownBy,
    DataClass,
    Evidence,
    Money,
    Period,
    PlanStatus,
    PlanType,
    RiskLevel,
    Role,
    SuggestionStatus,
    TargetType,
    UsageScope,
)
from schemas.entities import (
    ActionPlan,
    EmployeeProfile,
    PlanOpinion,
    Anomaly,
    BreakdownRow,
    Employee,
    EvalResult,
    Model,
    RegisteredTask,
    ToolWithPlan,
    UsageSummary,
    VendorUpdate,
)
from schemas.rest import (
    ContractInventory,
    RelevantTaskCandidate,
    SeatPaceDetail,
    TaskCostEstimateResponse,
    TeamAdoption,
)

ALL = [Role.employee, Role.admin, Role.system]


class Empty(BaseModel):
    pass


# ---------- 업무 MCP 입력 ----------
class UpsertMyTaskIn(BaseModel):
    task_id: str | None = Field(None, description="있으면 수정, 없으면 생성")
    title: str
    description: str
    frequency: str
    tools_used: list[str] = []


class ListApprovedToolsIn(BaseModel):
    category: str | None = Field(None, description="보통 비워 둔다(전체 조회). 'AI' 같은 말로 거르지 말 것. 코드값 예: chat_assistant, llm_api. AI/일반 SW 구분은 결과의 kind(ai|software)로 한다")


class ListApprovedModelsIn(BaseModel):
    data_class: DataClass | None = Field(None, description="보통 비워 둔다(전체 조회). 허용 데이터 등급으로 거를 때만 public|internal|confidential")


class FindRelevantTasksIn(BaseModel):
    update_id: str
    job_filter: list[str] | None = Field(None, description="직무명 필터")


class SaveSuggestionIn(BaseModel):
    update_id: str
    target_type: TargetType
    target_id: str | None = None
    task_id: str | None = None
    relevance: str = Field("", description="관련성 근거. on_hold가 아니면 비어 있을 때 서버가 invalid로 거절")
    body: str = ""
    status: SuggestionStatus | None = Field(None, description="on_hold면 보내지 않고 hold_reason만 남긴다 (회사 플랜에 없는 기능, 근거 없음 등)")
    hold_reason: str | None = None


class GetTeamAdoptionIn(BaseModel):
    team_id: str | None = None
    period: Period


class GetEvalResultsIn(BaseModel):
    task_type: str
    model_ids: list[str] | None = None


class EstimateTaskCostIn(BaseModel):
    model_id: str
    requests_per_day: int
    avg_input_tokens: int
    avg_output_tokens: int


class GetUsageSummaryIn(BaseModel):
    scope: UsageScope
    scope_id: str
    period: Period


class GetUsageBreakdownIn(BaseModel):
    project_id: str
    period: Period
    by: BreakdownBy


class GetAnomaliesIn(BaseModel):
    status: AnomalyStatus | None = None


class GetSeatUsageIn(BaseModel):
    employee_id: str = Field(description="직원은 본인 id만")


class GetLicenseInventoryIn(BaseModel):
    contract_id: str | None = None


class GetEmployeeAssetsIn(BaseModel):
    employee_id: str


class RequestConfirmationIn(BaseModel):
    employee_id: str
    plan_id: str
    question: str


class CreateActionPlanIn(BaseModel):
    type: PlanType
    items: list[dict]
    rationale: str
    evidence: list[Evidence]


class GetPlanStatusIn(BaseModel):
    plan_id: str


class GetEmployeeProfileIn(BaseModel):
    employee_id: str


class AttachPlanOpinionIn(BaseModel):
    plan_id: str
    opinion: PlanOpinion


class AttachPlanOpinionOut(BaseModel):
    plan_id: str
    status: PlanStatus


class ExecuteApprovedPlanIn(BaseModel):
    plan_id: str
    idempotency_key: str


# ---------- 업무 MCP 출력 ----------
class MyProfileOut(BaseModel):
    employee: Employee
    tasks: list[RegisteredTask]
    available_tools: list[ToolWithPlan]


class UpsertMyTaskOut(BaseModel):
    task_id: str


class ToolListOut(BaseModel):
    tools: list[ToolWithPlan]


class ModelListOut(BaseModel):
    models: list[Model]


class FindRelevantTasksOut(BaseModel):
    update: VendorUpdate
    candidates: list[RelevantTaskCandidate]


class SaveSuggestionOut(BaseModel):
    suggestion_id: str
    status: SuggestionStatus


class TeamAdoptionOut(BaseModel):
    teams: list[TeamAdoption]


class EvalResultsOut(BaseModel):
    task_type: str
    results: list[EvalResult]


class UsageBreakdownOut(BaseModel):
    project_id: str
    by: BreakdownBy
    rows: list[BreakdownRow]


class AnomaliesOut(BaseModel):
    anomalies: list[Anomaly]


class LicenseInventoryOut(BaseModel):
    contracts: list[ContractInventory]


class RequestConfirmationOut(BaseModel):
    confirmation_id: str
    due_at: datetime


class CreateActionPlanOut(BaseModel):
    plan_id: str
    risk_level: RiskLevel
    status: PlanStatus
    approvers_required: list[Role] = []


class PlanStatusOut(BaseModel):
    plan: ActionPlan


class ExecuteApprovedPlanOut(BaseModel):
    plan_id: str
    status: PlanStatus
    result: dict
    verified: dict


# ---------- 문서 검색 MCP ----------
class SearchVendorDocsIn(BaseModel):
    query: str
    vendor: str | None = None
    kind: str | None = None
    candidates_only: bool = False


class DocHit(BaseModel):
    vendor: str
    title: str
    excerpt: str
    url: str
    published_at: datetime | None = None
    score: float | None = None


class SearchVendorDocsOut(BaseModel):
    hits: list[DocHit]


class GetVendorUpdateIn(BaseModel):
    update_id: str


class SearchInternalPolicyIn(BaseModel):
    query: str


class PolicyHit(BaseModel):
    clause: str
    location: str = Field(description="문서명·절 번호")
    text: str


class SearchInternalPolicyOut(BaseModel):
    hits: list[PolicyHit]


# ---------- 레지스트리 ----------
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    roles: list[Role]
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = False
    backend: str = ""  # 호출하는 백엔드 REST 경로 (문서용)
    features: list[str] = field(default_factory=list)


WORK_TOOLS: list[ToolSpec] = [
    ToolSpec("get_my_profile", "요청자 본인의 직무, 부서, 등록 업무, 이용 가능 도구·플랜을 돌려준다.", Empty, MyProfileOut, ALL, backend="GET /me", features=["F1", "F2"]),
    ToolSpec("upsert_my_task", "본인 업무를 등록하거나 수정한다.", UpsertMyTaskIn, UpsertMyTaskOut, [Role.employee], read_only=False, backend="POST|PATCH /me/tasks", features=["F1"]),
    ToolSpec("list_approved_tools", "승인된 제품(AI·소프트웨어 구독)과 플랜, 과금 유형, 정책 요약을 돌려준다.", ListApprovedToolsIn, ToolListOut, ALL, backend="GET /tools", features=["F1", "F2", "F5"]),
    ToolSpec("list_approved_models", "승인된 모델과 단가, 허용 데이터 등급을 돌려준다.", ListApprovedModelsIn, ModelListOut, ALL, backend="GET /models", features=["F2"]),
    ToolSpec("find_relevant_tasks", "업데이트와 관련될 수 있는 등록 업무 후보를 돌려준다. 관리자에게는 팀 단위로만 보인다.", FindRelevantTasksIn, FindRelevantTasksOut, [Role.system, Role.admin], backend="GET /updates/{id}/relevant-tasks", features=["F1"]),
    ToolSpec("save_suggestion", "활용 제안을 저장한다. 보내지 않기로 했으면 status=on_hold와 hold_reason으로 사유를 남긴다. 보낼 때는 관련성 근거(relevance)가 필수다.", SaveSuggestionIn, SaveSuggestionOut, [Role.system, Role.admin], read_only=False, backend="POST /suggestions", features=["F1"]),
    ToolSpec("get_team_adoption", "팀별 제안 반응과 활동 인원 비율. 5명 미만 팀은 제외.", GetTeamAdoptionIn, TeamAdoptionOut, [Role.admin], backend="GET /adoption/teams", features=["F1"]),
    ToolSpec("get_eval_results", "업무 유형별 모델 품질 점수, 기준, 평균 토큰, 지연.", GetEvalResultsIn, EvalResultsOut, [Role.employee, Role.admin, Role.system], backend="GET /eval-results", features=["F2"]),
    ToolSpec("estimate_task_cost", "일·월 예상 비용을 코드로 계산한다. 계산식을 함께 돌려준다.", EstimateTaskCostIn, TaskCostEstimateResponse, ALL, backend="POST /estimates/task-cost", features=["F2"]),
    ToolSpec("get_usage_summary", "범위별 요청 수, 토큰, 비용, 마지막 활동 시각. 직원은 본인만.", GetUsageSummaryIn, UsageSummary, [Role.employee, Role.admin, Role.system], backend="GET /usage", features=["F2", "F3", "F4"]),
    ToolSpec("get_usage_breakdown", "프로젝트 사용량을 모델·API 키·입력 길이 구간별로 나눈다.", GetUsageBreakdownIn, UsageBreakdownOut, [Role.admin, Role.system], backend="GET /usage?group_by=", features=["F3"]),
    ToolSpec("get_anomalies", "사용량 경보 목록.", GetAnomaliesIn, AnomaliesOut, [Role.admin, Role.system], backend="GET /anomalies", features=["F3"]),
    ToolSpec("get_seat_usage", "좌석 한 명의 오늘 토큰 소비 속도(예상·평균 대비·한도 대비)와 시간대·입력 길이·모델별 분포. 직원은 본인만.", GetSeatUsageIn, SeatPaceDetail, ALL, backend="GET /usage/seats/{employee_id}", features=["F3"]),
    ToolSpec("get_license_inventory", "계약별 구매·배정·미배정 수와 저사용 후보. 기록 없음은 확인 필요로 표시.", GetLicenseInventoryIn, LicenseInventoryOut, [Role.admin, Role.system], backend="GET /inventory", features=["F4"]),
    ToolSpec("get_employee_assets", "직원 한 명이 지금 실제로 쓸 수 있는 도구(배정 좌석·팀 프로젝트 API)와 등록 업무. 부여·회수 전후 확인용.", GetEmployeeAssetsIn, MyProfileOut, [Role.admin, Role.system], backend="GET /employees/{id}/assets", features=["F4"]),
    ToolSpec("request_confirmation", "저사용 이용권 소유자에게 사용 의사를 묻는 요청을 만든다.", RequestConfirmationIn, RequestConfirmationOut, [Role.admin], read_only=False, backend="POST /confirmations", features=["F4"]),
    ToolSpec("create_action_plan", "처리 요청을 만든다. 모든 요청은 관리자 승인 대기로 들어가고(status=pending_approval), 에이전트가 직접 실행하지 않는다. 직원은 seat_assign(본인 이용권), seat_reclaim(본인 반납), api_access(API 제품 사용 신청), model_change(본인 소유 프로젝트, test 환경)를 만들 수 있다.", CreateActionPlanIn, CreateActionPlanOut, [Role.employee, Role.admin, Role.system], read_only=False, backend="POST /plans", features=["F1", "F2", "F3", "F4"]),
    ToolSpec("get_plan_status", "조치안 상태, 승인자, 결과.", GetPlanStatusIn, PlanStatusOut, ALL, backend="GET /plans/{id}", features=["common"]),
    ToolSpec("get_employee_profile", "검토용 직원 프로필: 이름·부서·직무·재직 상태·등록 업무·배정된 제품. 사용량·비밀번호는 없다.", GetEmployeeProfileIn, EmployeeProfile, [Role.system, Role.admin], backend="GET /employees/{id}", features=["F4"]),
    ToolSpec("attach_plan_opinion", "승인 대기 중인 처리 요청에 AI 검토 의견을 붙인다. 관리자가 읽으므로 전부 자연어·이름으로 쓴다.", AttachPlanOpinionIn, AttachPlanOpinionOut, [Role.system, Role.admin], read_only=False, backend="PATCH /plans/{id}/opinion", features=["F4"]),
    ToolSpec("execute_approved_plan", "승인된 조치안을 실행한다. 서버가 승인 상태와 대상 현재 상태를 재확인하고 다르면 stale로 멈춘다.", ExecuteApprovedPlanIn, ExecuteApprovedPlanOut, [Role.admin, Role.system], read_only=False, destructive=True, idempotent=True, backend="POST /plans/{id}/execute", features=["F2", "F4"]),
]

DOCS_TOOLS: list[ToolSpec] = [
    ToolSpec("search_vendor_docs", "허용 목록 벤더 공식 문서를 검색한다. 발췌와 원문 URL을 돌려준다.", SearchVendorDocsIn, SearchVendorDocsOut, ALL, backend="FTS5"),
    ToolSpec("get_vendor_update", "수집된 업데이트 한 건의 제목, 요약, 대상 플랜, 원문 URL.", GetVendorUpdateIn, VendorUpdate, ALL, backend="GET /updates/{id}"),
    ToolSpec("search_internal_policy", "사내 AI 사용 정책을 검색한다.", SearchInternalPolicyIn, SearchInternalPolicyOut, ALL, backend="FTS5"),
]

TOOLS = WORK_TOOLS + DOCS_TOOLS

RESOURCES: dict[str, str] = {
    "policy://ai-usage": "사내 AI 사용 정책 전문",
    "policy://notification": "알림 정책 (9절)",
    "policy://approval-matrix": "위험도별 승인 기준 (11절)",
    "catalog://approved-tools": "승인 도구·플랜 스냅샷",
    "contract://{id}/summary": "계약 요약",
    "me://profile": "요청자 본인 프로필·등록 업무",
}

PROMPTS: dict[str, list[str]] = {
    "review_update": ["update_id"],
    "draft_model_card": ["update_id"],
    "recommend_model": ["task_description"],
    "analyze_seat_usage": ["employee_id"],
    "review_seat_request": ["plan_id"],
    "review_plan": ["plan_id"],
}


def tools_for_role(role: Role) -> list[ToolSpec]:
    return [t for t in TOOLS if role in t.roles]


def tool_json_schema(spec: ToolSpec) -> dict:
    """MCP tools/list 항목 형태로 내보낸다."""
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": spec.input_model.model_json_schema(),
        "outputSchema": spec.output_model.model_json_schema(),
        "annotations": {
            "readOnlyHint": spec.read_only,
            "destructiveHint": spec.destructive,
            "idempotentHint": spec.idempotent,
        },
        "x-roles": [r.value for r in spec.roles],
        "x-backend": spec.backend,
    }
