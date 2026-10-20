"""백엔드 스텁. 8절 엔드포인트 전부가 고정 데이터로 동작한다.

B(백엔드)는 이 파일의 라우트 시그니처와 response_model을 유지한 채 내부를 DB 로직으로 바꾼다.
시그니처·모델을 바꿔야 하면 packages/schemas를 먼저 고치고 PR로 리드 리뷰를 받는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, Header, Query

from apps.backend import fixtures as fx
from apps.backend.auth import current_user, issue_token, require
from apps.backend.errors import ApiError, install_error_handlers, ok
from schemas.common import (
    RISK_BY_PLAN_TYPE,
    BreakdownBy,
    Envelope,
    ErrorCode,
    ErrorEnvelope,
    Granularity,
    LicenseFlag,
    Money,
    Page,
    PlanStatus,
    PlanType,
    RiskLevel,
    Role,
    SuggestionStatus,
    UsageScope,
)
from schemas.entities import (
    ActionPlan,
    Anomaly,
    AuditEntry,
    BreakdownRow,
    Confirmation,
    Employee,
    EvalResult,
    Model,
    RegisteredTask,
    Suggestion,
    ToolWithPlan,
    UsagePoint,
    UsageSummary,
    VendorUpdate,
)
from schemas.rest import (
    AnomalyDetail,
    ConfirmationAnswerRequest,
    ContractInventory,
    DevLoginRequest,
    DevLoginResponse,
    FeedbackCreate,
    JobRunResponse,
    LowUsageCandidate,
    MeResponse,
    PlanCreate,
    PlanDecision,
    PlanExecuteResponse,
    RelevantTaskCandidate,
    RelevantTasksResponse,
    SavingsSummary,
    SuggestionCreate,
    TaskCostEstimateRequest,
    TaskCostEstimateResponse,
    TaskCreate,
    TaskUpdate,
    TeamAdoption,
    UnmetNeedAggregate,
    UnmetNeedCreate,
    UnmetNeedCreateResponse,
    UsageResponse,
)

ALL = (Role.employee, Role.hrd, Role.asset, Role.approver, Role.system)
ERR = {401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope}}

app = FastAPI(title="AI 활용·운영 최적화 에이전트 — Backend API", version="0.1.0", responses=ERR)
install_error_handlers(app)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- auth / me ----------
@app.post("/auth/dev-login", response_model=Envelope[DevLoginResponse], tags=["auth"])
def dev_login(body: DevLoginRequest):
    emp = fx.EMPLOYEES.get(body.employee_id)
    if not emp:
        raise ApiError(ErrorCode.not_found, f"직원 {body.employee_id} 없음", {"available": list(fx.EMPLOYEES)})
    return ok(DevLoginResponse(access_token=issue_token(emp.id), employee=emp))


@app.get("/me", response_model=Envelope[MeResponse], tags=["me"])
def me(user: Employee = Depends(current_user)):
    tasks = [t for t in fx.TASKS.values() if t.employee_id == user.id]
    return ok(MeResponse(employee=user, tasks=tasks, available_tools=fx.TOOLS_WITH_PLAN[:2]))


@app.get("/me/tasks", response_model=Envelope[list[RegisteredTask]], tags=["me"])
def list_my_tasks(user: Employee = Depends(require(Role.employee))):
    return ok([t for t in fx.TASKS.values() if t.employee_id == user.id])


@app.post("/me/tasks", response_model=Envelope[RegisteredTask], status_code=201, tags=["me"])
def create_my_task(body: TaskCreate, user: Employee = Depends(require(Role.employee))):
    task = RegisteredTask(id=_new_id("task"), employee_id=user.id, updated_at=_now(), **body.model_dump())
    fx.TASKS[task.id] = task
    return ok(task)


@app.patch("/me/tasks/{task_id}", response_model=Envelope[RegisteredTask], tags=["me"])
def update_my_task(task_id: str, body: TaskUpdate, user: Employee = Depends(require(Role.employee))):
    task = fx.TASKS.get(task_id)
    if not task or task.employee_id != user.id:
        raise ApiError(ErrorCode.not_found, "본인 업무가 아니거나 없음")
    task = task.model_copy(update={**body.model_dump(exclude_none=True), "updated_at": _now()})
    fx.TASKS[task_id] = task
    return ok(task)


# ---------- catalog ----------
@app.get("/tools", response_model=Envelope[list[ToolWithPlan]], tags=["catalog"])
def list_tools(category: str | None = None, user: Employee = Depends(current_user)):
    items = fx.TOOLS_WITH_PLAN
    if category:
        items = [t for t in items if t.category == category]
    return ok(items)


@app.get("/models", response_model=Envelope[list[Model]], tags=["catalog"])
def list_models(user: Employee = Depends(current_user)):
    return ok(list(fx.MODELS.values()))


# ---------- updates / suggestions (F1) ----------
@app.get("/updates", response_model=Envelope[Page[VendorUpdate]], tags=["F1"])
def list_updates(limit: int = 50, offset: int = 0, user: Employee = Depends(current_user)):
    items = list(fx.UPDATES.values())
    return ok(Page(items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset))


@app.get("/updates/{update_id}", response_model=Envelope[VendorUpdate], tags=["F1"])
def get_update(update_id: str, user: Employee = Depends(current_user)):
    upd = fx.UPDATES.get(update_id)
    if not upd:
        raise ApiError(ErrorCode.not_found, "업데이트 없음")
    return ok(upd)


@app.get("/updates/{update_id}/relevant-tasks", response_model=Envelope[RelevantTasksResponse], tags=["F1"])
def relevant_tasks(update_id: str, job_filter: list[str] | None = Query(None), user: Employee = Depends(require(Role.system, Role.hrd))):
    upd = fx.UPDATES.get(update_id)
    if not upd:
        raise ApiError(ErrorCode.not_found, "업데이트 없음")
    cands = []
    for t in fx.TASKS.values():
        emp = fx.EMPLOYEES[t.employee_id]
        cands.append(RelevantTaskCandidate(
            task_id=t.id, job_title=emp.job_title, team_id=emp.dept_id,
            employee_id=emp.id if user.role == Role.system else None,  # HRD는 팀 단위만
            summary=f"{t.title}: {t.description}",
        ))
    return ok(RelevantTasksResponse(update=upd, candidates=cands))


@app.get("/suggestions", response_model=Envelope[Page[Suggestion]], tags=["F1"])
def list_suggestions(status: SuggestionStatus | None = None, update_id: str | None = None, user: Employee = Depends(require(Role.system, Role.hrd))):
    items = [s for s in fx.SUGGESTIONS.values() if (not status or s.status == status) and (not update_id or s.update_id == update_id)]
    return ok(Page(items=items, total=len(items)))


@app.post("/suggestions", response_model=Envelope[Suggestion], status_code=201, tags=["F1"])
def create_suggestion(body: SuggestionCreate, user: Employee = Depends(require(Role.system, Role.hrd))):
    if not body.relevance.strip():
        raise ApiError(ErrorCode.invalid, "관련성 근거(relevance) 없이는 제안을 저장할 수 없습니다")
    status = SuggestionStatus.draft if body.target_type.value == "employee" else SuggestionStatus.pending_approval
    s = Suggestion(id=_new_id("sug"), status=status, **body.model_dump())
    fx.SUGGESTIONS[s.id] = s
    return ok(s)


@app.post("/suggestions/{suggestion_id}/approve", response_model=Envelope[Suggestion], tags=["F1"])
def approve_suggestion(suggestion_id: str, user: Employee = Depends(require(Role.hrd))):
    s = fx.SUGGESTIONS.get(suggestion_id)
    if not s:
        raise ApiError(ErrorCode.not_found, "제안 없음")
    if s.status != SuggestionStatus.pending_approval:
        raise ApiError(ErrorCode.conflict, f"승인 대기 상태가 아님: {s.status.value}")
    s = s.model_copy(update={"status": SuggestionStatus.sent, "sent_at": _now()})
    fx.SUGGESTIONS[suggestion_id] = s
    return ok(s)


@app.post("/suggestions/{suggestion_id}/feedback", response_model=Envelope[dict], status_code=201, tags=["F1"])
def feedback(suggestion_id: str, body: FeedbackCreate, user: Employee = Depends(require(Role.employee, Role.hrd, Role.asset, Role.approver))):
    if suggestion_id not in fx.SUGGESTIONS:
        raise ApiError(ErrorCode.not_found, "제안 없음")
    return ok({"feedback_id": _new_id("fb"), "suggestion_id": suggestion_id, "reaction": body.reaction.value})


@app.get("/adoption/teams", response_model=Envelope[list[TeamAdoption]], tags=["F1"])
def adoption(team_id: str | None = None, user: Employee = Depends(require(Role.hrd))):
    rows = [
        TeamAdoption(team_id="dept_mkt", team_name="마케팅", headcount=24, suggestions_sent=18, useful=11, irrelevant=4, questions=3, active_ratio=0.71, top_questions=["이미지 생성 결과를 브랜드 가이드에 맞추는 법"]),
        TeamAdoption(team_id="dept_cs", team_name="고객지원", headcount=31, suggestions_sent=22, useful=9, irrelevant=10, questions=3, active_ratio=0.45),
    ]
    return ok([r for r in rows if not team_id or r.team_id == team_id])


# ---------- F2 ----------
@app.get("/eval-results", response_model=Envelope[list[EvalResult]], tags=["F2"])
def eval_results(task_type: str, model_ids: list[str] | None = Query(None), user: Employee = Depends(require(Role.employee, Role.asset, Role.system))):
    rows = [r for r in fx.EVAL_RESULTS if r.task_type == task_type and (not model_ids or r.model_id in model_ids)]
    return ok(rows)


@app.post("/estimates/task-cost", response_model=Envelope[TaskCostEstimateResponse], tags=["F2"])
def estimate(body: TaskCostEstimateRequest, user: Employee = Depends(current_user)):
    m = fx.MODELS.get(body.model_id)
    if not m:
        raise ApiError(ErrorCode.not_found, "모델 없음")
    daily_usd = body.requests_per_day * (body.avg_input_tokens * m.input_usd_per_mtok + body.avg_output_tokens * m.output_usd_per_mtok) / 1_000_000
    monthly_usd = daily_usd * body.working_days_per_month
    formula = (f"{body.requests_per_day}건 × ({body.avg_input_tokens}×${m.input_usd_per_mtok}/M + "
               f"{body.avg_output_tokens}×${m.output_usd_per_mtok}/M) = ${daily_usd:.2f}/일 × {body.working_days_per_month}일, 환율 {fx.FX:.0f}원")
    return ok(TaskCostEstimateResponse(model=m, daily=fx.krw(daily_usd), monthly=fx.krw(monthly_usd), fx_rate_krw_per_usd=fx.FX, formula=formula))


# ---------- F5 ----------
@app.get("/unmet-needs", response_model=Envelope[list[UnmetNeedAggregate]], tags=["F5"])
def list_unmet(min_count: int = 1, capability_tag: str | None = None, user: Employee = Depends(require(Role.hrd, Role.asset, Role.approver))):
    tags: dict[str, list] = {}
    for n in fx.UNMET_NEEDS:
        tags.setdefault(n.capability_tag, []).append(n)
    out = []
    for tag, needs in tags.items():
        depts = {n.dept_id for n in needs}
        agg = UnmetNeedAggregate(capability_tag=tag, count=len(needs), dept_count=len(depts), threshold_met=len(needs) >= 3 and len(depts) >= 2, sample_summaries=[n.summary for n in needs][:3])
        if agg.count >= min_count and (not capability_tag or tag == capability_tag):
            out.append(agg)
    return ok(out)


@app.post("/unmet-needs", response_model=Envelope[UnmetNeedCreateResponse], status_code=201, tags=["F5"])
def record_unmet(body: UnmetNeedCreate, user: Employee = Depends(require(Role.employee, Role.hrd, Role.asset))):
    from schemas.entities import UnmetNeed
    need = UnmetNeed(id=_new_id("need"), employee_id=user.id, dept_id=user.dept_id, created_at=_now(), **body.model_dump())
    fx.UNMET_NEEDS.append(need)
    same = [n for n in fx.UNMET_NEEDS if n.capability_tag == need.capability_tag]
    depts = {n.dept_id for n in same}
    return ok(UnmetNeedCreateResponse(need=need, same_tag_count=len(same), same_tag_dept_count=len(depts), threshold_met=len(same) >= 3 and len(depts) >= 2))


# ---------- F4 ----------
@app.get("/inventory", response_model=Envelope[list[ContractInventory]], tags=["F4"])
def inventory(contract_id: str | None = None, user: Employee = Depends(require(Role.asset, Role.approver, Role.system))):
    c = fx.CONTRACTS["ctr_ai_a_2026"]
    inv = ContractInventory(contract=c, tool_name="AI-A Enterprise Chat", purchased=60, assigned=58, unassigned=2, low_usage_candidates=[
        LowUsageCandidate(employee_id="emp_sales_02", employee_name="한도윤", dept_name="영업", last_activity_at=fx.NOW - timedelta(days=75), flag=LicenseFlag.on_leave, needs_confirmation=True),
        LowUsageCandidate(employee_id="emp_x_01", employee_name="(미사용 1)", dept_name="생산관리", last_activity_at=fx.NOW - timedelta(days=90), flag=LicenseFlag.unused, needs_confirmation=True),
        LowUsageCandidate(employee_id="emp_x_02", employee_name="(기록 없음)", dept_name="영업", last_activity_at=None, flag=LicenseFlag.no_record, needs_confirmation=True),
        LowUsageCandidate(employee_id="emp_x_03", employee_name="(최근 입사)", dept_name="마케팅", last_activity_at=None, flag=LicenseFlag.recent_hire, needs_confirmation=False),
    ])
    items = [inv]
    return ok([i for i in items if not contract_id or i.contract.id == contract_id])


# ---------- usage / anomalies (F3) ----------
def _series(days: int, base_usd: float, spike_last: int = 0, factor: float = 1.0) -> list[UsagePoint]:
    pts = []
    for i in range(days):
        day = fx.NOW - timedelta(days=days - 1 - i)
        usd = base_usd * (factor if i >= days - spike_last else 1.0)
        pts.append(UsagePoint(period_start=day.replace(hour=0, minute=0), requests=int(usd * 40), input_tokens=int(usd * 150_000), output_tokens=int(usd * 8_000), cost=fx.krw(usd)))
    return pts


@app.get("/usage", response_model=Envelope[UsageResponse], tags=["F3"])
def usage(scope: UsageScope, scope_id: str, start: datetime, end: datetime, granularity: Granularity = Granularity.day, group_by: BreakdownBy | None = None, user: Employee = Depends(require(Role.employee, Role.asset, Role.system))):
    if user.role == Role.employee and not (scope == UsageScope.employee and scope_id == user.id):
        raise ApiError(ErrorCode.forbidden, "직원은 본인 사용량만 조회할 수 있습니다")
    spike = scope_id == "prj_quote_summary"
    series = _series(14, 19.0, spike_last=2 if spike else 0, factor=3.1)
    total_usd = sum(p.cost.usd for p in series)
    summary = UsageSummary(scope=scope.value, scope_id=scope_id, period_start=start, period_end=end, requests=sum(p.requests for p in series), input_tokens=sum(p.input_tokens for p in series), output_tokens=sum(p.output_tokens for p in series), cost=fx.krw(total_usd), last_activity_at=fx.NOW - timedelta(hours=1))
    breakdown = []
    if group_by == BreakdownBy.model:
        breakdown = [BreakdownRow(key="b-large", requests=9000, input_tokens=30_000_000, output_tokens=1_500_000, cost=fx.krw(total_usd), share=1.0)]
    elif group_by == BreakdownBy.input_length:
        breakdown = [BreakdownRow(key="0-2k", requests=3000, input_tokens=3_000_000, output_tokens=500_000, cost=fx.krw(total_usd * 0.15), share=0.15),
                     BreakdownRow(key="2k-8k", requests=2000, input_tokens=9_000_000, output_tokens=500_000, cost=fx.krw(total_usd * 0.25), share=0.25),
                     BreakdownRow(key="8k+", requests=4000, input_tokens=18_000_000, output_tokens=500_000, cost=fx.krw(total_usd * 0.60), share=0.60)]
    elif group_by == BreakdownBy.api_key:
        breakdown = [BreakdownRow(key="key_sales_01", requests=9000, input_tokens=30_000_000, output_tokens=1_500_000, cost=fx.krw(total_usd), share=1.0)]
    return ok(UsageResponse(summary=summary, series=series, breakdown=breakdown))


@app.get("/anomalies", response_model=Envelope[list[Anomaly]], tags=["F3"])
def anomalies(status: str | None = None, user: Employee = Depends(require(Role.asset, Role.system))):
    return ok([a for a in fx.ANOMALIES.values() if not status or a.status.value == status])


@app.get("/anomalies/{anomaly_id}", response_model=Envelope[AnomalyDetail], tags=["F3"])
def anomaly_detail(anomaly_id: str, user: Employee = Depends(require(Role.asset, Role.system))):
    a = fx.ANOMALIES.get(anomaly_id)
    if not a:
        raise ApiError(ErrorCode.not_found, "경보 없음")
    series = _series(14, 19.0, spike_last=2, factor=3.1)
    total = sum(p.cost.usd for p in series)
    return ok(AnomalyDetail(anomaly=a, project=fx.PROJECTS.get(a.scope_id), series=series,
                            breakdown_by_model=[BreakdownRow(key="b-large", requests=9000, input_tokens=30_000_000, output_tokens=1_500_000, cost=fx.krw(total), share=1.0)],
                            breakdown_by_input_length=[BreakdownRow(key="8k+", requests=4000, input_tokens=18_000_000, output_tokens=500_000, cost=fx.krw(total * 0.6), share=0.6)]))


# ---------- plans (공통 실행 게이트) ----------
@app.get("/plans", response_model=Envelope[Page[ActionPlan]], tags=["plans"])
def list_plans(status: PlanStatus | None = None, type: PlanType | None = None, user: Employee = Depends(current_user)):
    items = [p for p in fx.PLANS.values() if (not status or p.status == status) and (not type or p.type == type)]
    if user.role == Role.employee:
        items = [p for p in items if p.requested_by == user.id]
    return ok(Page(items=items, total=len(items)))


@app.post("/plans", response_model=Envelope[ActionPlan], status_code=201, tags=["plans"])
def create_plan(body: PlanCreate, user: Employee = Depends(require(Role.employee, Role.hrd, Role.asset, Role.system))):
    allowed = {Role.employee: {PlanType.seat_assign}, Role.hrd: {PlanType.notice_send}}
    if user.role in allowed and body.type not in allowed[user.role]:
        raise ApiError(ErrorCode.forbidden, f"{user.role.value} 역할은 {body.type.value} 조치안을 만들 수 없습니다")
    risk = RISK_BY_PLAN_TYPE[body.type]
    if body.type == PlanType.model_change and any(i.get("environment") == "prod" for i in body.items):
        risk = RiskLevel.high
    status = PlanStatus.approved if risk == RiskLevel.low else PlanStatus.pending_approval
    plan = ActionPlan(id=_new_id("plan"), risk_level=risk, status=status, requested_by=user.id, created_at=_now(), **body.model_dump())
    fx.PLANS[plan.id] = plan
    return ok(plan)


@app.get("/plans/{plan_id}", response_model=Envelope[ActionPlan], tags=["plans"])
def get_plan(plan_id: str, user: Employee = Depends(current_user)):
    p = fx.PLANS.get(plan_id)
    if not p or (user.role == Role.employee and p.requested_by != user.id):
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    return ok(p)


def _decide(plan_id: str, body: PlanDecision, user: Employee, approve: bool) -> ActionPlan:
    p = fx.PLANS.get(plan_id)
    if not p:
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    if p.status != PlanStatus.pending_approval:
        raise ApiError(ErrorCode.conflict, f"승인 대기 상태가 아님: {p.status.value}")
    if p.risk_level == RiskLevel.high and user.role != Role.approver:
        raise ApiError(ErrorCode.forbidden, "높은 위험도는 승인자(IT·보안 책임자)만 결정할 수 있습니다")
    if p.type == PlanType.notice_send and user.role not in (Role.hrd, Role.approver):
        raise ApiError(ErrorCode.forbidden, "공지 발송은 HRD가 승인합니다")
    update = {"approver_id": user.id, "approved_at": _now(), "status": PlanStatus.approved} if approve else {"approver_id": user.id, "status": PlanStatus.rejected, "reject_reason": body.reason}
    p = p.model_copy(update=update)
    fx.PLANS[plan_id] = p
    return p


@app.post("/plans/{plan_id}/approve", response_model=Envelope[ActionPlan], tags=["plans"])
def approve_plan(plan_id: str, body: PlanDecision, user: Employee = Depends(require(Role.hrd, Role.asset, Role.approver))):
    return ok(_decide(plan_id, body, user, approve=True))


@app.post("/plans/{plan_id}/reject", response_model=Envelope[ActionPlan], tags=["plans"])
def reject_plan(plan_id: str, body: PlanDecision, user: Employee = Depends(require(Role.hrd, Role.asset, Role.approver))):
    return ok(_decide(plan_id, body, user, approve=False))


@app.post("/plans/{plan_id}/execute", response_model=Envelope[PlanExecuteResponse], tags=["plans"])
def execute_plan(plan_id: str, idempotency_key: str = Header(alias="Idempotency-Key"), user: Employee = Depends(require(Role.asset, Role.system))):
    p = fx.PLANS.get(plan_id)
    if not p:
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    if idempotency_key in fx.EXECUTIONS:  # 2. 같은 키면 첫 결과 그대로
        return ok(fx.EXECUTIONS[idempotency_key])
    if p.status != PlanStatus.approved:  # 1. 승인 아니면 403
        raise ApiError(ErrorCode.forbidden, f"승인 상태가 아님: {p.status.value}")
    if p.risk_level == RiskLevel.high:
        raise ApiError(ErrorCode.forbidden, "높은 위험도 조치는 MVP에서 실행하지 않습니다 (요청만 생성)")
    # 3. 재검증 (스텁: items에 stale=True가 있으면 중단)
    if any(i.get("_stale") for i in p.items):
        raise ApiError(ErrorCode.stale, "승인 뒤 대상 상태가 바뀌어 실행을 멈췄습니다", {"plan_id": plan_id})
    # 4. 실행기(Mock 벤더) 호출 + 재조회 (스텁)
    executed = p.model_copy(update={"status": PlanStatus.executed, "executed_at": _now(), "result": {"vendor": "mock", "ok": True}})
    fx.PLANS[plan_id] = executed
    resp = PlanExecuteResponse(plan=executed, result={"vendor": "mock", "ok": True, "items": p.items}, verified={"items": p.items, "state": "applied"}, savings=[s.model_dump() for s in fx.SAVINGS if s.plan_id == plan_id])
    fx.EXECUTIONS[idempotency_key] = resp
    return ok(resp)


@app.post("/confirmations/{confirmation_id}/answer", response_model=Envelope[Confirmation], tags=["F4"])
def answer_confirmation(confirmation_id: str, body: ConfirmationAnswerRequest, user: Employee = Depends(require(Role.employee))):
    c = fx.CONFIRMATIONS.get(confirmation_id)
    if not c:
        raise ApiError(ErrorCode.not_found, "확인 요청 없음")
    if c.employee_id != user.id:
        raise ApiError(ErrorCode.forbidden, "본인에게 온 확인 요청만 답할 수 있습니다")
    c = c.model_copy(update={"answer": body.answer, "answered_at": _now()})
    fx.CONFIRMATIONS[confirmation_id] = c
    return ok(c)


# ---------- savings / audit / jobs ----------
@app.get("/savings", response_model=Envelope[SavingsSummary], tags=["F4"])
def savings(user: Employee = Depends(require(Role.asset, Role.approver))):
    by: dict = {}
    for s in fx.SAVINGS:
        by[s.kind] = by.get(s.kind, 0) + s.amount_krw
    return ok(SavingsSummary(by_kind=by, total_krw=sum(by.values())))


@app.get("/audit-log", response_model=Envelope[Page[AuditEntry]], tags=["audit"])
def audit_log(limit: int = 50, offset: int = 0, user: Employee = Depends(require(Role.asset, Role.approver))):
    return ok(Page(items=fx.AUDIT[offset : offset + limit], total=len(fx.AUDIT), limit=limit, offset=offset))


JOBS = {"collect_release_notes", "collect_usage", "check_thresholds", "aggregate_unmet_needs"}


@app.post("/internal/jobs/{job_name}/run", response_model=Envelope[JobRunResponse], tags=["internal"])
def run_job(job_name: str, user: Employee = Depends(require(Role.system, Role.asset))):
    if job_name not in JOBS:
        raise ApiError(ErrorCode.not_found, f"배치 없음. 가능: {sorted(JOBS)}")
    t = _now()
    return ok(JobRunResponse(job=job_name, started_at=t, finished_at=t, result={"stub": True, "new_items": 1}))
