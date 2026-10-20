"""Harness 2. Tools — MCP Client로 도구를 가져오고, 결과 길이를 제한하고, 오류는 ToolMessage로 돌려준다.

두 모드:
- MCP 모드 (MCP_WORK_URL 설정): langchain-mcp-adapters로 업무 MCP·문서 검색 MCP의 tools/list를 받는다.
  요청자 토큰을 헤더로 넘기므로 역할별로 보이는 도구가 다르다.
- 로컬 모드 (기본): schemas.mcp_tools.TOOLS 정의 그대로 백엔드 REST를 직접 부른다.
  MCP 서버가 준비되기 전 개발·시연용이며, 도구 이름·입출력은 MCP 모드와 같다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from langchain_core.tools import BaseTool, StructuredTool

from apps.agent_runtime.config import BACKEND_URL, MCP_DOCS_URL, MCP_WORK_URL, TOOL_RESULT_MAX_CHARS
from apps.agent_runtime.harness.guardrails import mask_pii
from apps.agent_runtime.harness.instructions import policy_text
from schemas.common import Role
from schemas.mcp_tools import ToolSpec, tools_for_role

TRANSPORT_OVERRIDE: httpx.AsyncBaseTransport | None = None  # 테스트에서 ASGITransport를 꽂는다


def backend_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BACKEND_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30, transport=TRANSPORT_OVERRIDE)


def shape_result(raw) -> str:
    """도구 결과를 문자열로 만들고, 길이를 자르고, 개인정보를 가린다."""
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, list):  # MCP content blocks
        text = "\n".join(b.get("text", json.dumps(b, ensure_ascii=False)) if isinstance(b, dict) else str(b) for b in raw)
    else:
        text = json.dumps(raw, ensure_ascii=False, default=str)
    if len(text) > TOOL_RESULT_MAX_CHARS:
        text = text[:TOOL_RESULT_MAX_CHARS] + f"\n...[잘림: 전체 {len(text)}자]"
    return mask_pii(text)


# ---------- 로컬 모드: 도구 이름 → 백엔드 REST ----------
async def _call(client: httpx.AsyncClient, method: str, path: str, *, params: dict | None = None, json_body: dict | None = None, headers: dict | None = None):
    params = {k: v for k, v in (params or {}).items() if v is not None}
    r = await client.request(method, path, params=params, json=json_body, headers=headers)
    body = r.json()
    if "error" in body:
        return {"error": body["error"]}  # 오류도 데이터로 돌려준다 (ToolMessage)
    return body["data"]


def _period(p: dict) -> dict:
    return {"start": f"{p['start']}T00:00:00Z", "end": f"{p['end']}T23:59:59Z"}


async def local_call(name: str, args: dict, client: httpx.AsyncClient):  # noqa: C901
    a = args
    match name:
        case "get_my_profile":
            return await _call(client, "GET", "/me")
        case "upsert_my_task":
            if a.get("task_id"):
                return {"task_id": (await _call(client, "PATCH", f"/me/tasks/{a['task_id']}", json_body={k: v for k, v in a.items() if k != "task_id"}))["id"]}
            return {"task_id": (await _call(client, "POST", "/me/tasks", json_body={k: v for k, v in a.items() if k != "task_id"}))["id"]}
        case "list_approved_tools":
            return {"tools": await _call(client, "GET", "/tools", params={"category": a.get("category")})}
        case "list_approved_models":
            models = await _call(client, "GET", "/models")
            if a.get("data_class") and isinstance(models, list):
                models = [m for m in models if m["allowed_data_class"] == a["data_class"]]
            return {"models": models}
        case "find_relevant_tasks":
            return await _call(client, "GET", f"/updates/{a['update_id']}/relevant-tasks", params={"job_filter": a.get("job_filter")})
        case "save_suggestion":
            d = await _call(client, "POST", "/suggestions", json_body=a)
            return d if "error" in d else {"suggestion_id": d["id"], "status": d["status"]}
        case "get_team_adoption":
            return {"teams": await _call(client, "GET", "/adoption/teams", params={"team_id": a.get("team_id")})}
        case "get_eval_results":
            return {"task_type": a["task_type"], "results": await _call(client, "GET", "/eval-results", params={"task_type": a["task_type"], "model_ids": a.get("model_ids")})}
        case "estimate_task_cost":
            return await _call(client, "POST", "/estimates/task-cost", json_body=a)
        case "get_usage_summary":
            d = await _call(client, "GET", "/usage", params={"scope": a["scope"], "scope_id": a["scope_id"], **_period(a["period"])})
            return d if "error" in d else d["summary"]
        case "get_usage_breakdown":
            d = await _call(client, "GET", "/usage", params={"scope": "project", "scope_id": a["project_id"], "group_by": a["by"], **_period(a["period"])})
            return d if "error" in d else {"project_id": a["project_id"], "by": a["by"], "rows": d["breakdown"]}
        case "get_anomalies":
            return {"anomalies": await _call(client, "GET", "/anomalies", params={"status": a.get("status")})}
        case "get_license_inventory":
            return {"contracts": await _call(client, "GET", "/inventory", params={"contract_id": a.get("contract_id")})}
        case "record_unmet_need":
            d = await _call(client, "POST", "/unmet-needs", json_body=a)
            return d if "error" in d else {"need_id": d["need"]["id"], "same_tag_count": d["same_tag_count"], "threshold_met": d["threshold_met"]}
        case "list_unmet_needs":
            return {"aggregates": await _call(client, "GET", "/unmet-needs", params={"min_count": a.get("min_count"), "capability_tag": a.get("capability_tag")})}
        case "request_confirmation":
            return {"error": {"code": "invalid", "message": "로컬 모드에서는 사용 의사 확인 요청을 만들 수 없습니다. seat_reclaim 조치안에 confirmation_id를 넣어 주세요."}}
        case "create_action_plan":
            d = await _call(client, "POST", "/plans", json_body=a)
            return d if "error" in d else {"plan_id": d["id"], "risk_level": d["risk_level"], "status": d["status"]}
        case "get_plan_status":
            d = await _call(client, "GET", f"/plans/{a['plan_id']}")
            return d if "error" in d else {"plan": d}
        case "execute_approved_plan":
            d = await _call(client, "POST", f"/plans/{a['plan_id']}/execute", headers={"Idempotency-Key": a["idempotency_key"]})
            return d if "error" in d else {"plan_id": a["plan_id"], "status": d["plan"]["status"], "result": d["result"], "verified": d["verified"]}
        case "search_vendor_docs":
            page = await _call(client, "GET", "/updates")
            if "error" in page:
                return page
            q = a["query"].lower()
            hits = [u for u in page["items"] if (not a.get("vendor") or u["vendor"] == a["vendor"]) and any(w in (u["title"] + u["summary"]).lower() for w in q.split())]
            return {"hits": [{"vendor": u["vendor"], "title": u["title"], "excerpt": u["summary"], "url": u["url"], "published_at": u["published_at"]} for u in hits]}
        case "get_vendor_update":
            return await _call(client, "GET", f"/updates/{a['update_id']}")
        case "search_internal_policy":
            text = policy_text("ai_usage")
            q = a["query"].lower()
            paras = [p for p in text.split("\n\n") if any(w in p.lower() for w in q.split())]
            return {"hits": [{"clause": p[:40], "location": "policy://ai-usage", "text": p} for p in paras[:5]]}
    return {"error": {"code": "not_found", "message": f"도구 {name} 없음"}}


def _local_tool(spec: ToolSpec, token: str) -> BaseTool:
    async def run(**kwargs):
        args = spec.input_model(**kwargs).model_dump(mode="json", exclude_none=True)  # enum·모델 → JSON 타입
        async with backend_client(token) as client:
            return await local_call(spec.name, args, client)

    return StructuredTool.from_function(coroutine=run, name=spec.name, description=spec.description, args_schema=spec.input_model)


# ---------- MCP 모드 ----------
_MCP_CACHE: dict[str, list[BaseTool]] = {}


async def _mcp_tools(token: str) -> list[BaseTool]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    if token in _MCP_CACHE:
        return _MCP_CACHE[token]
    headers = {"Authorization": f"Bearer {token}"}
    conns = {"work": {"url": MCP_WORK_URL, "transport": "streamable_http", "headers": headers}}
    if MCP_DOCS_URL:
        conns["docs"] = {"url": MCP_DOCS_URL, "transport": "streamable_http", "headers": headers}
    client = MultiServerMCPClient(conns)
    tools = await client.get_tools()
    _MCP_CACHE[token] = tools
    return tools


async def load_tools(token: str, role: Role) -> list[BaseTool]:
    if MCP_WORK_URL:
        return await _mcp_tools(token)
    return [_local_tool(spec, token) for spec in tools_for_role(role)]


def new_idempotency_key() -> str:
    return f"idem_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


ToolLoader = Callable[[str, Role], list[BaseTool]]
