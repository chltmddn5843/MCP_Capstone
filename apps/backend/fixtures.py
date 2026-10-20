"""스텁용 고정 데이터 (10절 시드 '한빛제조' 축약판). 실제 DB가 붙으면 이 파일은 사라진다."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from schemas.common import *  # noqa: F403
from schemas.entities import *  # noqa: F403

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
FX = 1380.0


def krw(usd: float) -> Money:
    return Money(krw=round(usd * FX), usd=round(usd, 4))


DEPARTMENTS = {d.id: d for d in [
    Department(id="dept_mgmt", name="경영지원"),
    Department(id="dept_hrd", name="HRD"),
    Department(id="dept_mkt", name="마케팅"),
    Department(id="dept_sales", name="영업"),
    Department(id="dept_cs", name="고객지원"),
    Department(id="dept_prod", name="생산관리"),
]}

EMPLOYEES = {e.id: e for e in [
    Employee(id="emp_hrd_01", name="김하나", email="hana.kim@hanbit.example", dept_id="dept_hrd", dept_name="HRD", role=Role.employee, job_title="교육기획", slack_user_id="U_HRD01"),
    Employee(id="emp_mkt_01", name="박서준", email="seojun.park@hanbit.example", dept_id="dept_mkt", dept_name="마케팅", role=Role.employee, job_title="콘텐츠 마케터", slack_user_id="U_MKT01"),
    Employee(id="emp_cs_01", name="이지우", email="jiwoo.lee@hanbit.example", dept_id="dept_cs", dept_name="고객지원", role=Role.employee, job_title="CS 운영", slack_user_id="U_CS01"),
    Employee(id="emp_asset_01", name="최민준", email="minjun.choi@hanbit.example", dept_id="dept_mgmt", dept_name="경영지원", role=Role.admin, job_title="IT 자산·보안 관리자", slack_user_id="U_ADM01"),
    Employee(id="emp_sales_02", name="한도윤", email="doyun.han@hanbit.example", dept_id="dept_sales", dept_name="영업", role=Role.employee, job_title="영업 담당", status=EmployeeStatus.on_leave),
    Employee(id="sys", name="system", email="system@hanbit.example", dept_id="dept_mgmt", role=Role.system, job_title="batch"),
]}

TOOLS = {t.id: t for t in [
    Tool(id="tool_ai_a", vendor="AI-A", product="AI-A Enterprise Chat", category="chat_assistant", approval_status=ToolApprovalStatus.approved, allowed_data_class=DataClass.internal, policy_note="고객 개인정보 입력 금지"),
    Tool(id="tool_ai_b", vendor="AI-B", product="AI-B API", category="llm_api", approval_status=ToolApprovalStatus.approved, allowed_data_class=DataClass.internal),
    Tool(id="tool_cand_x", vendor="Vendor-X", product="X Docs AI", category="chat_assistant", approval_status=ToolApprovalStatus.under_review, allowed_data_class=DataClass.public, policy_note="비교 후보. 계약 없음"),
]}

CONTRACTS = {c.id: c for c in [
    Contract(id="ctr_ai_a_2026", tool_id="tool_ai_a", plan_name="Enterprise (seat + usage)", billing_type=BillingType.seat_plus_usage, seats_purchased=60, seat_price_krw=45000, term_start=datetime(2026, 1, 1, tzinfo=UTC), term_end=datetime(2026, 12, 31, tzinfo=UTC)),
    Contract(id="ctr_ai_b_2026", tool_id="tool_ai_b", plan_name="API pay-as-you-go", billing_type=BillingType.api_usage, seats_purchased=0, seat_price_krw=0, term_start=datetime(2026, 1, 1, tzinfo=UTC), term_end=datetime(2026, 12, 31, tzinfo=UTC)),
]}

TOOLS_WITH_PLAN = [
    ToolWithPlan(**TOOLS["tool_ai_a"].model_dump(), contract=CONTRACTS["ctr_ai_a_2026"]),
    ToolWithPlan(**TOOLS["tool_ai_b"].model_dump(), contract=CONTRACTS["ctr_ai_b_2026"]),
    ToolWithPlan(**TOOLS["tool_cand_x"].model_dump()),
]

MODELS = {m.id: m for m in [
    Model(id="mdl_b_large", vendor="AI-B", name="b-large", input_usd_per_mtok=3.0, output_usd_per_mtok=15.0, allowed_data_class=DataClass.internal),
    Model(id="mdl_b_mid", vendor="AI-B", name="b-mid", input_usd_per_mtok=0.8, output_usd_per_mtok=4.0, allowed_data_class=DataClass.internal),
    Model(id="mdl_b_small", vendor="AI-B", name="b-small", input_usd_per_mtok=0.25, output_usd_per_mtok=1.25, allowed_data_class=DataClass.internal),
]}

TASKS = {t.id: t for t in [
    RegisteredTask(id="task_hrd_survey", employee_id="emp_hrd_01", title="교육 과정별 설문 결과 비교", description="과정별 만족도 설문 파일을 비교해 공통 개선점과 과정별 차이를 정리", frequency="monthly", tools_used=["tool_ai_a"], updated_at=NOW - timedelta(days=10)),
    RegisteredTask(id="task_mkt_copy", employee_id="emp_mkt_01", title="캠페인 카피 초안 작성", description="제품 소개 문구 3안 작성", frequency="weekly", tools_used=["tool_ai_a"], updated_at=NOW - timedelta(days=3)),
    RegisteredTask(id="task_cs_classify", employee_id="emp_cs_01", title="고객 문의 유형 분류", description="하루 1,000건 문의를 10개 유형으로 분류 (API)", frequency="daily", tools_used=["tool_ai_b"], updated_at=NOW - timedelta(days=30)),
]}

UPDATES = {u.id: u for u in [
    VendorUpdate(id="upd_ai_a_doc_compare", source_id="src_ai_a_rn", vendor="AI-A", published_at=NOW - timedelta(days=1), title="문서 비교 기능 추가", summary="여러 파일을 함께 올리고 차이점과 공통점을 표로 정리할 수 있다. Enterprise 플랜부터 제공.", url="https://vendor-a.example/release-notes/2026-10-19", affected_plans=["Enterprise"], fetched_at=NOW),
    VendorUpdate(id="upd_ai_b_price", source_id="src_ai_b_rn", vendor="AI-B", published_at=NOW - timedelta(days=5), title="b-mid 입력 단가 인하", summary="b-mid 입력 토큰 단가 20% 인하.", url="https://vendor-b.example/release-notes/2026-10-15", affected_plans=["API"], fetched_at=NOW),
]}

SUGGESTIONS = {s.id: s for s in [
    Suggestion(id="sug_001", update_id="upd_ai_a_doc_compare", target_type=TargetType.employee, target_id="emp_hrd_01", task_id="task_hrd_survey", relevance="등록 업무 '교육 과정별 설문 결과 비교'가 여러 파일 비교를 필요로 함", body="등록하신 '교육 과정별 설문 결과 비교' 업무에 쓸 수 있는 기능이 추가됐어요. ...", status=SuggestionStatus.draft),
]}

EVAL_RESULTS = [
    EvalResult(id="ev_001", task_type="customer_inquiry_classification", model_id="mdl_b_large", quality_score=0.94, threshold=0.90, passed=True, avg_input_tokens=600, avg_output_tokens=20, latency_ms=1800, evaluated_at=NOW - timedelta(days=14)),
    EvalResult(id="ev_002", task_type="customer_inquiry_classification", model_id="mdl_b_mid", quality_score=0.92, threshold=0.90, passed=True, avg_input_tokens=600, avg_output_tokens=20, latency_ms=900, evaluated_at=NOW - timedelta(days=14)),
    EvalResult(id="ev_003", task_type="customer_inquiry_classification", model_id="mdl_b_small", quality_score=0.84, threshold=0.90, passed=False, avg_input_tokens=600, avg_output_tokens=20, latency_ms=500, evaluated_at=NOW - timedelta(days=14)),
]

PROJECTS = {p.id: p for p in [
    Project(id="prj_cs_classify", name="고객 문의 분류", dept_id="dept_cs", owner_id="emp_cs_01", purpose="문의 자동 분류", model_id="mdl_b_large", environment=Environment.prod, monthly_budget_krw=1500000),
    Project(id="prj_quote_summary", name="견적서 요약", dept_id="dept_sales", owner_id="emp_sales_02", purpose="견적서 PDF 요약", model_id="mdl_b_large", environment=Environment.prod, monthly_budget_krw=800000),
    Project(id="prj_faq", name="사내 FAQ", dept_id="dept_mgmt", owner_id="emp_asset_01", purpose="사내 규정 Q&A", model_id="mdl_b_mid", environment=Environment.test, monthly_budget_krw=300000),
]}

ANOMALIES = {a.id: a for a in [
    Anomaly(id="anm_001", scope_type="project", scope_id="prj_quote_summary", scope_name="견적서 요약", rule="daily_cost_gt_3x_baseline", baseline=26000, observed=81000, ratio=3.1, projected_monthly_cost=krw(1760), status=AnomalyStatus.open, created_at=NOW - timedelta(hours=2)),
]}

PLANS = {p.id: p for p in [
    ActionPlan(id="plan_001", type=PlanType.seat_assign, risk_level=RiskLevel.low, status=PlanStatus.approved, items=[{"employee_id": "emp_mkt_01", "contract_id": "ctr_ai_a_2026"}], rationale="미배정 좌석 2석 중 1석 배정", evidence=[Evidence(source="inventory", ref="ctr_ai_a_2026", value={"unassigned": 2})], requested_by="emp_mkt_01", approver_id=None, created_at=NOW - timedelta(minutes=30)),
    ActionPlan(id="plan_002", type=PlanType.seat_reclaim, risk_level=RiskLevel.medium, status=PlanStatus.pending_approval, items=[{"employee_id": "emp_sales_02", "contract_id": "ctr_ai_a_2026"}], rationale="휴직 중, 본인 확인 응답: 반납", evidence=[Evidence(source="confirmations", ref="cfm_001", value="return_seat")], requested_by="emp_asset_01", created_at=NOW - timedelta(minutes=10)),
]}

CONFIRMATIONS = {c.id: c for c in [
    Confirmation(id="cfm_001", plan_id="plan_002", employee_id="emp_sales_02", question="AI-A 이용권을 계속 사용하시나요?", due_at=NOW + timedelta(days=5)),
]}

UNMET_NEEDS = [
    UnmetNeed(id="need_001", employee_id="emp_sales_02", dept_id="dept_sales", summary="계약서 두 버전 조항 비교", capability_tag="contract_compare", created_at=NOW - timedelta(days=6)),
    UnmetNeed(id="need_002", employee_id="emp_mkt_01", dept_id="dept_mkt", summary="협력사 계약서 변경점 확인", capability_tag="contract_compare", created_at=NOW - timedelta(days=2)),
]

SAVINGS = [SavingsEntry(id="sav_001", plan_id="plan_001", kind=SavingsKind.purchase_avoided, amount_krw=45000 * 2, basis="재배정 1석 × 월 45,000원 × 남은 2개월")]

AUDIT = [AuditEntry(id="aud_001", actor_id="emp_asset_01", actor_role=Role.admin, action="plan.approve", target="plan_001", before={"status": "pending_approval"}, after={"status": "approved"}, created_at=NOW - timedelta(minutes=20))]

EXECUTIONS: dict[str, dict] = {}  # idempotency_key -> 첫 실행 결과
