"""백엔드 스텁. 8절 엔드포인트 전부가 고정 데이터로 동작한다.

B(백엔드)는 이 파일의 라우트 시그니처와 response_model을 유지한 채 내부를 DB 로직으로 바꾼다.
DB 전환 완료: 인증(직원 조회), F4(이용권·처리 요청·확인 요청·절감), 감사 로그. 나머지는 아직 fixtures.
시그니처·모델을 바꿔야 하면 packages/schemas를 먼저 고치고 PR로 리드 리뷰를 받는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, Header, Query

from apps.backend import db
from apps.backend import fixtures as fx
from apps.backend.auth import current_user, get_employee, issue_token, require
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
    SavingsKind,
    SuggestionStatus,
    UsageScope,
)
from schemas.entities import (
    ActionPlan,
    Contract,
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
from pydantic import ValidationError

from schemas.plan_items import validate_items
from schemas.rest import (
    AnomalyDetail,
    ConfirmationAnswerRequest,
    ConfirmationCreate,
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

ALL = (Role.employee, Role.admin, Role.system)
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
    emp = get_employee(body.employee_id)
    if not emp:
        raise ApiError(ErrorCode.not_found, f"직원 {body.employee_id} 없음")
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
def relevant_tasks(update_id: str, job_filter: list[str] | None = Query(None), user: Employee = Depends(require(Role.system, Role.admin))):
    upd = fx.UPDATES.get(update_id)
    if not upd:
        raise ApiError(ErrorCode.not_found, "업데이트 없음")
    cands = []
    for t in fx.TASKS.values():
        emp = fx.EMPLOYEES[t.employee_id]
        cands.append(RelevantTaskCandidate(
            task_id=t.id, job_title=emp.job_title, team_id=emp.dept_id,
            employee_id=emp.id if user.role == Role.system else None,  # 관리자는 팀 단위만
            summary=f"{t.title}: {t.description}",
        ))
    return ok(RelevantTasksResponse(update=upd, candidates=cands))


@app.get("/suggestions", response_model=Envelope[Page[Suggestion]], tags=["F1"])
def list_suggestions(status: SuggestionStatus | None = None, update_id: str | None = None, user: Employee = Depends(require(Role.system, Role.admin))):
    items = [s for s in fx.SUGGESTIONS.values() if (not status or s.status == status) and (not update_id or s.update_id == update_id)]
    return ok(Page(items=items, total=len(items)))


@app.post("/suggestions", response_model=Envelope[Suggestion], status_code=201, tags=["F1"])
def create_suggestion(body: SuggestionCreate, user: Employee = Depends(require(Role.system, Role.admin))):
    if body.status == SuggestionStatus.on_hold:
        if not (body.hold_reason or "").strip():
            raise ApiError(ErrorCode.invalid, "보류(on_hold)에는 hold_reason이 필요합니다")
        status = SuggestionStatus.on_hold
    else:
        if not body.relevance.strip():
            raise ApiError(ErrorCode.invalid, "관련성 근거(relevance) 없이는 제안을 보낼 수 없습니다. 보내지 않으려면 status=on_hold와 hold_reason을 쓰세요")
        if not body.body.strip():
            raise ApiError(ErrorCode.invalid, "제안 본문(body)이 비어 있습니다")
        status = SuggestionStatus.draft if body.target_type.value == "employee" else SuggestionStatus.pending_approval
    s = Suggestion(id=_new_id("sug"), **body.model_dump(exclude={"status"}), status=status)
    fx.SUGGESTIONS[s.id] = s
    return ok(s)


@app.post("/suggestions/{suggestion_id}/feedback", response_model=Envelope[dict], status_code=201, tags=["F1"])
def feedback(suggestion_id: str, body: FeedbackCreate, user: Employee = Depends(require(Role.employee, Role.admin))):
    if suggestion_id not in fx.SUGGESTIONS:
        raise ApiError(ErrorCode.not_found, "제안 없음")
    return ok({"feedback_id": _new_id("fb"), "suggestion_id": suggestion_id, "reaction": body.reaction.value})


@app.get("/adoption/teams", response_model=Envelope[list[TeamAdoption]], tags=["F1"])
def adoption(team_id: str | None = None, user: Employee = Depends(require(Role.admin))):
    rows = [
        TeamAdoption(team_id="dept_mkt", team_name="마케팅", headcount=24, suggestions_sent=18, useful=11, irrelevant=4, questions=3, active_ratio=0.71, top_questions=["이미지 생성 결과를 브랜드 가이드에 맞추는 법"]),
        TeamAdoption(team_id="dept_cs", team_name="고객지원", headcount=31, suggestions_sent=22, useful=9, irrelevant=10, questions=3, active_ratio=0.45),
    ]
    return ok([r for r in rows if not team_id or r.team_id == team_id])


# ---------- F2 ----------
@app.get("/eval-results", response_model=Envelope[list[EvalResult]], tags=["F2"])
def eval_results(task_type: str, model_ids: list[str] | None = Query(None), user: Employee = Depends(require(Role.employee, Role.admin, Role.system))):
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
def list_unmet(min_count: int = 1, capability_tag: str | None = None, user: Employee = Depends(require(Role.admin))):
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
def record_unmet(body: UnmetNeedCreate, user: Employee = Depends(require(Role.employee, Role.admin, Role.system))):
    from schemas.entities import UnmetNeed
    need = UnmetNeed(id=_new_id("need"), employee_id=user.id, dept_id=user.dept_id, created_at=_now(), **body.model_dump())
    fx.UNMET_NEEDS.append(need)
    same = [n for n in fx.UNMET_NEEDS if n.capability_tag == need.capability_tag]
    depts = {n.dept_id for n in same}
    return ok(UnmetNeedCreateResponse(need=need, same_tag_count=len(same), same_tag_dept_count=len(depts), threshold_met=len(same) >= 3 and len(depts) >= 2))


# ---------- F4 ----------
@app.get("/inventory", response_model=Envelope[list[ContractInventory]], tags=["F4"])
def inventory(contract_id: str | None = None, user: Employee = Depends(require(Role.admin, Role.system))):
    contracts = db.rows(
        "SELECT c.id, c.tool_id, c.plan_name, c.billing_type, c.seats_purchased, c.seat_price_krw,"
        " c.term_start::timestamptz AS term_start, c.term_end::timestamptz AS term_end, c.mid_term_reduction,"
        " t.product AS tool_name, count(s.id) AS assigned"
        " FROM contracts c JOIN tools t ON t.id = c.tool_id"
        " LEFT JOIN seat_assignments s ON s.contract_id = c.id AND s.status = 'assigned'"
        " WHERE c.seats_purchased > 0 AND (CAST(:cid AS varchar) IS NULL OR c.id = :cid)"
        " GROUP BY c.id, t.product, t.kind ORDER BY t.kind, c.id", cid=contract_id)
    cands = db.rows(
        "SELECT s.contract_id, s.employee_id, e.name AS employee_name, d.name AS dept_name, s.last_activity_at, s.flag"
        " FROM seat_assignments s JOIN employees e ON e.id = s.employee_id JOIN departments d ON d.id = e.dept_id"
        " WHERE s.status = 'assigned' AND s.flag IS NOT NULL ORDER BY s.last_activity_at NULLS FIRST")
    out = []
    for c in contracts:
        low = [LowUsageCandidate(**{k: v for k, v in x.items() if k != "contract_id"}, needs_confirmation=x["flag"] != LicenseFlag.recent_hire.value)
               for x in cands if x["contract_id"] == c["id"]]
        out.append(ContractInventory(contract=Contract(**c), tool_name=c["tool_name"], purchased=c["seats_purchased"],
                                     assigned=c["assigned"], unassigned=c["seats_purchased"] - c["assigned"], low_usage_candidates=low))
    return ok(out)


# ---------- usage / anomalies (F3) ----------
def _series(days: int, base_usd: float, spike_last: int = 0, factor: float = 1.0) -> list[UsagePoint]:
    pts = []
    for i in range(days):
        day = fx.NOW - timedelta(days=days - 1 - i)
        usd = base_usd * (factor if i >= days - spike_last else 1.0)
        pts.append(UsagePoint(period_start=day.replace(hour=0, minute=0), requests=int(usd * 40), input_tokens=int(usd * 150_000), output_tokens=int(usd * 8_000), cost=fx.krw(usd)))
    return pts


@app.get("/usage", response_model=Envelope[UsageResponse], tags=["F3"])
def usage(scope: UsageScope, scope_id: str, start: datetime, end: datetime, granularity: Granularity = Granularity.day, group_by: BreakdownBy | None = None, user: Employee = Depends(require(Role.employee, Role.admin, Role.system))):
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
def anomalies(status: str | None = None, user: Employee = Depends(require(Role.admin, Role.system))):
    return ok([a for a in fx.ANOMALIES.values() if not status or a.status.value == status])


@app.get("/anomalies/{anomaly_id}", response_model=Envelope[AnomalyDetail], tags=["F3"])
def anomaly_detail(anomaly_id: str, user: Employee = Depends(require(Role.admin, Role.system))):
    a = fx.ANOMALIES.get(anomaly_id)
    if not a:
        raise ApiError(ErrorCode.not_found, "경보 없음")
    series = _series(14, 19.0, spike_last=2, factor=3.1)
    total = sum(p.cost.usd for p in series)
    return ok(AnomalyDetail(anomaly=a, project=fx.PROJECTS.get(a.scope_id), series=series,
                            breakdown_by_model=[BreakdownRow(key="b-large", requests=9000, input_tokens=30_000_000, output_tokens=1_500_000, cost=fx.krw(total), share=1.0)],
                            breakdown_by_input_length=[BreakdownRow(key="8k+", requests=4000, input_tokens=18_000_000, output_tokens=500_000, cost=fx.krw(total * 0.6), share=0.6)]))


# ---------- plans (공통 실행 게이트) ----------
PLAN_COLS = "id, type, risk_level, status, items, rationale, evidence, ai_opinion, requested_by, approver_id, approved_at, reject_reason, execution_key, executed_at, result, created_at"


def _plan(plan_id: str, conn=None) -> ActionPlan | None:
    r = db.one(f"SELECT {PLAN_COLS} FROM action_plans WHERE id = :id", conn, id=plan_id)
    return ActionPlan(**r) if r else None


def _audit(conn, user: Employee, action: str, target: str, before: dict | None, after: dict | None) -> None:
    conn.execute(db.text("INSERT INTO audit_log (id, actor_id, actor_role, action, target, before, after, created_at)"
                         " VALUES (:id, :a, :r, :act, :t, CAST(:b AS jsonb), CAST(:af AS jsonb), now())"),
                 dict(id=_new_id("aud"), a=user.id, r=user.role.value, act=action, t=target, b=db.js(before), af=db.js(after)))


@app.get("/plans", response_model=Envelope[Page[ActionPlan]], tags=["plans"])
def list_plans(status: PlanStatus | None = None, type: PlanType | None = None, user: Employee = Depends(current_user)):
    rs = db.rows(f"SELECT {PLAN_COLS} FROM action_plans WHERE (CAST(:s AS plan_status) IS NULL OR status = CAST(:s AS plan_status))"
                 " AND (CAST(:t AS plan_type) IS NULL OR type = CAST(:t AS plan_type))"
                 " AND (CAST(:me AS varchar) IS NULL OR requested_by = :me) ORDER BY created_at DESC",
                 s=status and status.value, t=type and type.value, me=user.id if user.role == Role.employee else None)
    items = [ActionPlan(**r) for r in rs]
    return ok(Page(items=items, total=len(items)))


@app.post("/plans", response_model=Envelope[ActionPlan], status_code=201, tags=["plans"])
def create_plan(body: PlanCreate, user: Employee = Depends(require(Role.employee, Role.admin, Role.system))):
    allowed = {Role.employee: {PlanType.seat_assign, PlanType.model_change}}
    if user.role in allowed and body.type not in allowed[user.role]:
        raise ApiError(ErrorCode.forbidden, f"{user.role.value} 역할은 {body.type.value} 조치안을 만들 수 없습니다")
    if user.role == Role.employee and body.type == PlanType.seat_assign and any(i.get("employee_id") != user.id for i in body.items):
        raise ApiError(ErrorCode.forbidden, "직원은 본인 이용권만 신청할 수 있습니다")
    if user.role == Role.employee and body.type == PlanType.model_change:  # 시나리오 B: 본인 프로젝트의 테스트 환경만
        for i in body.items:
            prj = db.one("SELECT owner_id FROM projects WHERE id = :id", id=i.get("project_id", ""))
            if not prj or prj["owner_id"] != user.id:
                raise ApiError(ErrorCode.forbidden, "직원은 본인이 오너인 프로젝트의 모델 변경만 요청할 수 있습니다", {"project_id": i.get("project_id")})
            if i.get("environment", "test") != "test":
                raise ApiError(ErrorCode.forbidden, "직원은 테스트 환경 변경만 요청할 수 있습니다. 운영 환경은 자산관리가 요청합니다")
    try:
        items = validate_items(body.type, body.items)
    except ValidationError as e:
        raise ApiError(ErrorCode.invalid, f"{body.type.value} 조치안의 items 형식이 맞지 않습니다", {"errors": e.errors()})
    risk = RISK_BY_PLAN_TYPE[body.type]
    if body.type == PlanType.model_change and any(i.get("environment") == "prod" for i in items):
        risk = RiskLevel.high
    status = PlanStatus.approved if risk == RiskLevel.low else PlanStatus.pending_approval
    pid = _new_id("plan")
    with db.tx() as c:
        c.execute(db.text("INSERT INTO action_plans (id, type, risk_level, status, items, rationale, evidence, requested_by, created_at)"
                          " VALUES (:id, :ty, :rk, :st, CAST(:it AS jsonb), :ra, CAST(:ev AS jsonb), :by, now())"),
                  dict(id=pid, ty=body.type.value, rk=risk.value, st=status.value, it=db.js(items), ra=body.rationale,
                       ev=db.js([e.model_dump() for e in body.evidence]), by=user.id))
        _audit(c, user, "plan.create", pid, None, {"status": status.value, "risk_level": risk.value})
    plan = _plan(pid)
    if risk == RiskLevel.low:  # 11절: 낮은 위험(되돌릴 수 있는 조치)은 승인 없이 즉시 실행하고 사후 기록
        plan = _execute(plan, f"auto_{pid}", user).plan
    return ok(plan)


@app.get("/plans/{plan_id}", response_model=Envelope[ActionPlan], tags=["plans"])
def get_plan(plan_id: str, user: Employee = Depends(current_user)):
    p = _plan(plan_id)
    if not p or (user.role == Role.employee and p.requested_by != user.id):
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    return ok(p)


def _decide(plan_id: str, body: PlanDecision, user: Employee, approve: bool) -> ActionPlan:
    with db.tx() as c:
        # 상태 전이는 조건부 UPDATE 한 번. 동시에 두 명이 눌러도 한 명만 성공한다
        n = c.execute(db.text("UPDATE action_plans SET status = CAST(:st AS plan_status), approver_id = :u,"
                              " approved_at = CASE WHEN :ap THEN now() END, reject_reason = CASE WHEN :ap THEN NULL ELSE :rs END"
                              " WHERE id = :id AND status = 'pending_approval'"),
                      dict(st="approved" if approve else "rejected", u=user.id, ap=approve, rs=body.reason, id=plan_id)).rowcount
        if n == 0:
            p = _plan(plan_id, c)
            if not p:
                raise ApiError(ErrorCode.not_found, "조치안 없음")
            raise ApiError(ErrorCode.conflict, f"승인 대기 상태가 아님: {p.status.value}")
        _audit(c, user, "plan.approve" if approve else "plan.reject", plan_id, {"status": "pending_approval"},
               {"status": "approved" if approve else "rejected", "reason": body.reason})
    return _plan(plan_id)


@app.post("/plans/{plan_id}/approve", response_model=Envelope[ActionPlan], tags=["plans"])
def approve_plan(plan_id: str, body: PlanDecision, user: Employee = Depends(require(Role.admin))):
    return ok(_decide(plan_id, body, user, approve=True))


@app.post("/plans/{plan_id}/reject", response_model=Envelope[ActionPlan], tags=["plans"])
def reject_plan(plan_id: str, body: PlanDecision, user: Employee = Depends(require(Role.admin))):
    return ok(_decide(plan_id, body, user, approve=False))


SEAT_SQL = {
    PlanType.seat_assign: "INSERT INTO seat_assignments (id, contract_id, employee_id, status, assigned_at) VALUES (:sid, :c, :e, 'assigned', now())"
                          " ON CONFLICT (contract_id, employee_id) WHERE status = 'assigned' DO NOTHING",
    PlanType.seat_reclaim: "UPDATE seat_assignments SET status = 'unassigned', unassigned_at = now() WHERE contract_id = :c AND employee_id = :e AND status = 'assigned'",
}


def _exec_response(p: ActionPlan) -> PlanExecuteResponse:
    sv = db.rows("SELECT id, plan_id, kind, amount_krw, basis FROM savings_ledger WHERE plan_id = :id ORDER BY id", id=p.id)
    return PlanExecuteResponse(plan=p, result=p.result, verified={"items": p.items, "state": "applied"}, savings=sv)


def _execute(p: ActionPlan, idempotency_key: str, user: Employee) -> PlanExecuteResponse:
    """실행기. 1) 멱등 키 2) 승인 상태 3) 대상 재검증 4) 좌석 반영 5) 절감 기록. 한 트랜잭션."""
    if p.status == PlanStatus.executed:
        if db.one("SELECT execution_key FROM action_plans WHERE id = :id", id=p.id)["execution_key"] == idempotency_key:  # 같은 키면 첫 결과 그대로
            return _exec_response(p)
        raise ApiError(ErrorCode.conflict, "이미 다른 실행 키로 실행된 조치안입니다", {"plan_id": p.id})
    if p.status != PlanStatus.approved:
        raise ApiError(ErrorCode.forbidden, f"승인 상태가 아님: {p.status.value}")
    if p.risk_level == RiskLevel.high:
        raise ApiError(ErrorCode.forbidden, "높은 위험도 조치는 MVP에서 실행하지 않습니다 (요청만 생성)")
    if any(i.get("_stale") for i in p.items):  # 스텁: 재검증 실패 흉내
        raise ApiError(ErrorCode.stale, "승인 뒤 대상 상태가 바뀌어 실행을 멈췄습니다", {"plan_id": p.id})
    result = {"vendor": "mock", "ok": True, "items": p.items}
    with db.tx() as c:
        n = c.execute(db.text("UPDATE action_plans SET status = 'executed', executed_at = now(), execution_key = :k, result = CAST(:r AS jsonb)"
                              " WHERE id = :id AND status = 'approved'"), dict(k=idempotency_key, r=db.js(result), id=p.id)).rowcount
        if n == 0:  # 그 사이 다른 요청이 실행했다
            raise ApiError(ErrorCode.stale, "실행 직전에 상태가 바뀌었습니다", {"plan_id": p.id})
        for i in p.items if p.type in SEAT_SQL else []:
            c.execute(db.text(SEAT_SQL[p.type]), dict(sid=_new_id("seat"), c=i["contract_id"], e=i["employee_id"]))
        if p.type == PlanType.seat_assign:
            c.execute(db.text("INSERT INTO savings_ledger (id, plan_id, kind, amount_krw, basis) VALUES (:id, :p, 'purchase_avoided', 90000,"
                              " '미배정 좌석 배정으로 추가 구매 회피 (월 45,000원 × 남은 2개월)')"), dict(id=_new_id("sav"), p=p.id))
        _audit(c, user, "plan.execute", p.id, {"status": "approved"}, {"status": "executed", "key": idempotency_key})
    return _exec_response(_plan(p.id))


@app.post("/plans/{plan_id}/execute", response_model=Envelope[PlanExecuteResponse], tags=["plans"])
def execute_plan(plan_id: str, idempotency_key: str = Header(alias="Idempotency-Key"), user: Employee = Depends(require(Role.admin, Role.system))):
    p = _plan(plan_id)
    if not p:
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    return ok(_execute(p, idempotency_key, user))


def _add_business_days(start: datetime, days: int) -> datetime:
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


CFM_COLS = "id, plan_id, employee_id, question, answer, due_at, answered_at"


@app.post("/confirmations", response_model=Envelope[Confirmation], status_code=201, tags=["F4"])
def create_confirmation(body: ConfirmationCreate, user: Employee = Depends(require(Role.admin, Role.system))):
    if not get_employee(body.employee_id):
        raise ApiError(ErrorCode.not_found, "직원 없음")
    if not _plan(body.plan_id):
        raise ApiError(ErrorCode.not_found, "조치안 없음")
    # 같은 조치안·직원에 이미 보낸 확인 요청이 있으면 그것을 돌려준다 (UNIQUE plan_id, employee_id)
    r = db.one(f"SELECT {CFM_COLS} FROM confirmations WHERE plan_id = :p AND employee_id = :e", p=body.plan_id, e=body.employee_id)
    if not r:
        with db.tx() as c:
            r = db.one(f"INSERT INTO confirmations (id, plan_id, employee_id, question, due_at) VALUES (:id, :p, :e, :q, :due) RETURNING {CFM_COLS}", c,
                       id=_new_id("cfm"), p=body.plan_id, e=body.employee_id, q=body.question, due=_add_business_days(_now(), 5))
    return ok(Confirmation(**r))


@app.post("/confirmations/{confirmation_id}/answer", response_model=Envelope[Confirmation], tags=["F4"])
def answer_confirmation(confirmation_id: str, body: ConfirmationAnswerRequest, user: Employee = Depends(require(Role.employee))):
    r = db.one(f"SELECT {CFM_COLS} FROM confirmations WHERE id = :id", id=confirmation_id)
    if not r:
        raise ApiError(ErrorCode.not_found, "확인 요청 없음")
    if r["employee_id"] != user.id:
        raise ApiError(ErrorCode.forbidden, "본인에게 온 확인 요청만 답할 수 있습니다")
    with db.tx() as c:
        r = db.one(f"UPDATE confirmations SET answer = :a, answered_at = now() WHERE id = :id RETURNING {CFM_COLS}", c, a=body.answer.value, id=confirmation_id)
    return ok(Confirmation(**r))


# ---------- savings / audit / jobs ----------
@app.get("/savings", response_model=Envelope[SavingsSummary], tags=["F4"])
def savings(user: Employee = Depends(require(Role.admin))):
    by = {r["kind"]: r["total"] for r in db.rows("SELECT kind, sum(amount_krw)::int AS total FROM savings_ledger GROUP BY kind")}
    return ok(SavingsSummary(by_kind=by, total_krw=sum(by.values())))


@app.get("/audit-log", response_model=Envelope[Page[AuditEntry]], tags=["audit"])
def audit_log(limit: int = 50, offset: int = 0, user: Employee = Depends(require(Role.admin))):
    rs = db.rows("SELECT id, actor_id, actor_role, action, target, before, after, created_at FROM audit_log ORDER BY created_at DESC LIMIT :l OFFSET :o", l=limit, o=offset)
    total = db.one("SELECT count(*) AS n FROM audit_log")["n"]
    return ok(Page(items=[AuditEntry(**r) for r in rs], total=total, limit=limit, offset=offset))


JOBS = {"collect_release_notes", "collect_usage", "check_thresholds", "aggregate_unmet_needs"}


@app.post("/internal/jobs/{job_name}/run", response_model=Envelope[JobRunResponse], tags=["internal"])
def run_job(job_name: str, user: Employee = Depends(require(Role.system, Role.admin))):
    if job_name not in JOBS:
        raise ApiError(ErrorCode.not_found, f"배치 없음. 가능: {sorted(JOBS)}")
    t = _now()
    return ok(JobRunResponse(job=job_name, started_at=t, finished_at=t, result={"stub": True, "new_items": 1}))
