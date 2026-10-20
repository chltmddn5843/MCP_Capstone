"""도구별 백엔드 호출. schemas.mcp_tools의 ToolSpec.backend 경로를 그대로 부르고,
응답을 ToolSpec.output_model 모양으로 맞춘다. 업무 규칙은 백엔드에 있고 여기서는 모양만 바꾼다.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import time

from pydantic import BaseModel
from schemas import mcp_tools as M
from schemas.common import DataClass, PlanType, RiskLevel, Role, UsageScope

from apps.mcp_work.backend import call

Adapter = Callable[[BaseModel], Awaitable[dict]]
ADAPTERS: dict[str, Adapter] = {}

DATA_CLASS_RANK = {DataClass.public: 0, DataClass.internal: 1, DataClass.confidential: 2}


def adapter(name: str):
    def register(fn: Adapter) -> Adapter:
        ADAPTERS[name] = fn
        return fn
    return register


def _period(period) -> dict:
    """Period(date)를 백엔드 /usage의 start·end(datetime)로 바꾼다. end는 그날 끝까지."""
    return {"start": f"{period.start.isoformat()}T00:00:00Z",
            "end": f"{period.end.isoformat()}T{time(23, 59, 59).isoformat()}Z"}


# ---------- 프로필·업무 ----------
@adapter("get_my_profile")
async def get_my_profile(_: M.Empty) -> dict:
    return await call("GET", "/me")


@adapter("upsert_my_task")
async def upsert_my_task(i: M.UpsertMyTaskIn) -> dict:
    body = i.model_dump(exclude={"task_id"})
    if i.task_id:
        task = await call("PATCH", f"/me/tasks/{i.task_id}", json_body=body)
    else:
        task = await call("POST", "/me/tasks", json_body={**body, "source": "bot"})
    return {"task_id": task["id"]}


# ---------- 카탈로그 ----------
@adapter("list_approved_tools")
async def list_approved_tools(i: M.ListApprovedToolsIn) -> dict:
    return {"tools": await call("GET", "/tools", params={"category": i.category})}


@adapter("list_approved_models")
async def list_approved_models(i: M.ListApprovedModelsIn) -> dict:
    models = await call("GET", "/models")
    if i.data_class:  # 요청한 데이터 등급 이상을 허용하는 모델만
        need = DATA_CLASS_RANK[i.data_class]
        models = [m for m in models if DATA_CLASS_RANK[DataClass(m["allowed_data_class"])] >= need]
    return {"models": models}


# ---------- F1 업데이트·제안 ----------
@adapter("find_relevant_tasks")
async def find_relevant_tasks(i: M.FindRelevantTasksIn) -> dict:
    return await call("GET", f"/updates/{i.update_id}/relevant-tasks", params={"job_filter": i.job_filter})


@adapter("save_suggestion")
async def save_suggestion(i: M.SaveSuggestionIn) -> dict:
    s = await call("POST", "/suggestions", json_body=i.model_dump(mode="json"))
    return {"suggestion_id": s["id"], "status": s["status"]}


@adapter("get_team_adoption")
async def get_team_adoption(i: M.GetTeamAdoptionIn) -> dict:
    return {"teams": await call("GET", "/adoption/teams", params={"team_id": i.team_id, **_period(i.period)})}


# ---------- F2 모델 선택 ----------
@adapter("get_eval_results")
async def get_eval_results(i: M.GetEvalResultsIn) -> dict:
    rows = await call("GET", "/eval-results", params={"task_type": i.task_type, "model_ids": i.model_ids})
    return {"task_type": i.task_type, "results": rows}


@adapter("estimate_task_cost")
async def estimate_task_cost(i: M.EstimateTaskCostIn) -> dict:
    return await call("POST", "/estimates/task-cost", json_body=i.model_dump())


# ---------- F3 사용량·경보 ----------
@adapter("get_usage_summary")
async def get_usage_summary(i: M.GetUsageSummaryIn) -> dict:
    data = await call("GET", "/usage", params={"scope": i.scope.value, "scope_id": i.scope_id, **_period(i.period)})
    return data["summary"]


@adapter("get_usage_breakdown")
async def get_usage_breakdown(i: M.GetUsageBreakdownIn) -> dict:
    data = await call("GET", "/usage", params={"scope": UsageScope.project.value, "scope_id": i.project_id,
                                               "group_by": i.by.value, **_period(i.period)})
    return {"project_id": i.project_id, "by": i.by.value, "rows": data["breakdown"]}


@adapter("get_anomalies")
async def get_anomalies(i: M.GetAnomaliesIn) -> dict:
    return {"anomalies": await call("GET", "/anomalies", params={"status": i.status and i.status.value})}


@adapter("get_anomaly_detail")
async def get_anomaly_detail(i: M.GetAnomalyDetailIn) -> dict:
    return await call("GET", f"/anomalies/{i.anomaly_id}")


# ---------- F4 이용권 ----------
@adapter("get_license_inventory")
async def get_license_inventory(i: M.GetLicenseInventoryIn) -> dict:
    return {"contracts": await call("GET", "/inventory", params={"contract_id": i.contract_id})}


@adapter("request_confirmation")
async def request_confirmation(i: M.RequestConfirmationIn) -> dict:
    c = await call("POST", "/confirmations", json_body=i.model_dump())
    return {"confirmation_id": c["id"], "due_at": c["due_at"]}


# ---------- F5 미충족 수요 ----------
@adapter("record_unmet_need")
async def record_unmet_need(i: M.RecordUnmetNeedIn) -> dict:
    r = await call("POST", "/unmet-needs", json_body=i.model_dump())
    return {"need_id": r["need"]["id"], "same_tag_count": r["same_tag_count"], "threshold_met": r["threshold_met"]}


@adapter("list_unmet_needs")
async def list_unmet_needs(i: M.ListUnmetNeedsIn) -> dict:
    return {"aggregates": await call("GET", "/unmet-needs", params=i.model_dump())}


# ---------- 조치안 (공통 실행 게이트) ----------
def _approvers(plan_type: PlanType, risk: RiskLevel) -> list[str]:
    """누가 승인해야 하는지. 백엔드 _decide 규칙(11절)을 에이전트 안내용으로 옮겨 적은 것이다."""
    if risk == RiskLevel.low:
        return []
    if risk == RiskLevel.high:
        return [Role.approver.value]
    if plan_type == PlanType.notice_send:
        return [Role.hrd.value]
    return [Role.asset.value]


@adapter("create_action_plan")
async def create_action_plan(i: M.CreateActionPlanIn) -> dict:
    plan = await call("POST", "/plans", json_body=i.model_dump(mode="json"))
    risk = RiskLevel(plan["risk_level"])
    approvers = _approvers(PlanType(plan["type"]), risk) if plan["status"] == "pending_approval" else []
    return {"plan_id": plan["id"], "risk_level": risk.value, "status": plan["status"], "approvers_required": approvers}


@adapter("get_plan_status")
async def get_plan_status(i: M.GetPlanStatusIn) -> dict:
    return {"plan": await call("GET", f"/plans/{i.plan_id}")}


@adapter("execute_approved_plan")
async def execute_approved_plan(i: M.ExecuteApprovedPlanIn) -> dict:
    r = await call("POST", f"/plans/{i.plan_id}/execute", headers={"Idempotency-Key": i.idempotency_key})
    return {"plan_id": r["plan"]["id"], "status": r["plan"]["status"], "result": r["result"], "verified": r["verified"]}

