"""계약 테스트. 모든 엔드포인트가 봉투 형식과 response_model을 지키는지 확인한다.
백엔드가 DB로 바뀌어도 이 테스트는 그대로 통과해야 한다.
"""

import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app
from schemas.common import Role
from schemas.mcp_tools import TOOLS, tools_for_role
from schemas.rest import ROUTES

client = TestClient(app, raise_server_exceptions=True)


def login(employee_id: str) -> dict:
    r = client.post("/auth/dev-login", json={"employee_id": employee_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


HRD, EMP, ASSET, APPROVER, SYS = (login(i) for i in ["emp_hrd_01", "emp_mkt_01", "emp_asset_01", "emp_approver_01", "sys"])


def test_envelope_success_and_error():
    assert set(client.get("/me", headers=EMP).json()) == {"data", "meta"}
    r = client.get("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    r = client.get("/inventory", headers=HRD)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_routes_table_matches_app():
    """schemas.rest.ROUTES 표와 실제 라우터가 같아야 한다."""
    app_routes = {(m, r.path) for r in app.routes for m in getattr(r, "methods", []) if m != "HEAD"}
    spec_routes = {(m, p) for m, p, _, _ in ROUTES}
    assert spec_routes == {x for x in app_routes if not x[1].startswith(("/openapi", "/docs", "/redoc"))}


def test_hrd_sees_team_only_candidates():
    data = client.get("/updates/upd_ai_a_doc_compare/relevant-tasks", headers=HRD).json()["data"]
    assert all(c["employee_id"] is None for c in data["candidates"])
    data = client.get("/updates/upd_ai_a_doc_compare/relevant-tasks", headers=SYS).json()["data"]
    assert all(c["employee_id"] for c in data["candidates"])


def test_suggestion_requires_relevance():
    body = {"update_id": "upd_ai_a_doc_compare", "target_type": "employee", "target_id": "emp_hrd_01", "relevance": " ", "body": "x"}
    assert client.post("/suggestions", json=body, headers=SYS).status_code == 422


def test_estimate_formula():
    body = {"model_id": "mdl_b_mid", "requests_per_day": 1000, "avg_input_tokens": 600, "avg_output_tokens": 20}
    d = client.post("/estimates/task-cost", json=body, headers=EMP).json()["data"]
    assert d["monthly"]["krw"] > 0 and "formula" in d


def test_plan_lifecycle_and_idempotency():
    plan = client.post("/plans", json={"type": "seat_reclaim", "items": [{"employee_id": "emp_sales_02", "contract_id": "ctr_ai_a_2026"}], "rationale": "휴직", "evidence": [{"source": "confirmations", "ref": "cfm_001"}]}, headers=ASSET).json()["data"]
    assert plan["status"] == "pending_approval" and plan["risk_level"] == "medium"
    pid = plan["id"]
    # 승인 전 실행 → 403
    assert client.post(f"/plans/{pid}/execute", headers={**ASSET, "Idempotency-Key": "k1"}).status_code == 403
    # 사유 없는 승인 → 422
    assert client.post(f"/plans/{pid}/approve", json={"reason": ""}, headers=ASSET).status_code == 422
    assert client.post(f"/plans/{pid}/approve", json={"reason": "본인 반납 응답"}, headers=ASSET).json()["data"]["status"] == "approved"
    r1 = client.post(f"/plans/{pid}/execute", headers={**ASSET, "Idempotency-Key": "k1"}).json()["data"]
    r2 = client.post(f"/plans/{pid}/execute", headers={**ASSET, "Idempotency-Key": "k1"}).json()["data"]
    assert r1 == r2 and r1["plan"]["status"] == "executed"


def test_high_risk_only_approver_and_never_executed():
    plan = client.post("/plans", json={"type": "purchase_review", "items": [{"tool_id": "tool_cand_x"}], "rationale": "수요 3건", "evidence": []}, headers=ASSET).json()["data"]
    pid = plan["id"]
    assert plan["risk_level"] == "high"
    assert client.post(f"/plans/{pid}/approve", json={"reason": "ok"}, headers=ASSET).status_code == 403
    assert client.post(f"/plans/{pid}/approve", json={"reason": "ok"}, headers=APPROVER).status_code == 200
    assert client.post(f"/plans/{pid}/execute", headers={**ASSET, "Idempotency-Key": "k2"}).status_code == 403


def test_employee_usage_self_only():
    q = {"scope": "project", "scope_id": "prj_quote_summary", "start": "2026-10-01T00:00:00Z", "end": "2026-10-20T00:00:00Z"}
    assert client.get("/usage", params=q, headers=EMP).status_code == 403
    assert client.get("/usage", params={**q, "group_by": "input_length"}, headers=ASSET).status_code == 200


def test_mcp_registry_roles_and_schemas():
    names = [t.name for t in TOOLS]
    assert len(names) == len(set(names)) == 22
    assert "execute_approved_plan" not in {t.name for t in tools_for_role(Role.employee)}
    assert "get_usage_breakdown" in {t.name for t in tools_for_role(Role.asset)}
    for t in TOOLS:
        t.input_model.model_json_schema()
        t.output_model.model_json_schema()


@pytest.mark.parametrize("method,path", [(m, p) for m, p, _, _ in ROUTES if "{" not in p and m == "GET" and p not in ("/usage", "/eval-results")])
def test_every_simple_get_responds_in_envelope(method, path):
    r = client.get(path, headers=SYS if path not in ("/adoption/teams", "/me/tasks", "/savings", "/audit-log", "/unmet-needs") else {**HRD, **({} if path in ("/adoption/teams", "/unmet-needs") else ASSET)})
    assert r.status_code in (200, 403), (path, r.text)
    assert ("data" in r.json()) or ("error" in r.json())
