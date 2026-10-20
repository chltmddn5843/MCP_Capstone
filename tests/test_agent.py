"""에이전트 런타임 통합 테스트. 스크립트 모델(키 불필요)로 그래프·승인 interrupt·재개·이벤트를 확인한다."""

import json
import os
import time

os.environ["LLM_MODEL"] = "fake"
os.environ["AGENT_CHECKPOINT_DB"] = ":memory:"
os.environ["AGENT_TASK_DB"] = ":memory:"
os.environ["MCP_WORK_URL"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.agent_runtime.harness import tools as tools_mod  # noqa: E402
from apps.agent_runtime.main import app as agent_app  # noqa: E402
from apps.backend.main import app as backend_app  # noqa: E402

tools_mod.TRANSPORT_OVERRIDE = httpx.ASGITransport(app=backend_app)
EMP = {"Authorization": "Bearer dev.emp_mkt_01"}
ASSET = {"Authorization": "Bearer dev.emp_asset_01"}


def events(c: TestClient, task_id: str, headers: dict, after: int = 0) -> list[dict]:
    out = []
    with c.stream("GET", f"/ai/tasks/{task_id}/stream", params={"after": after}, headers=headers, timeout=30) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                out.append(json.loads(line[5:]))
    return out


def wait_status(c: TestClient, task_id: str, headers: dict, wanted: set[str], timeout: float = 10) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"/ai/tasks/{task_id}", headers=headers).json()["data"]
        if t["status"] in wanted:
            return t
        time.sleep(0.1)
    raise AssertionError(f"timeout waiting {wanted}, last={t['status']} error={t.get('error')}")


@pytest.fixture(scope="module")
def client():
    with TestClient(agent_app) as c:
        yield c


def test_auth_required(client):
    assert client.post("/ai/tasks", json={"input": "hi"}).status_code == 401


def test_profile_question_runs_to_done_with_evidence(client):
    r = client.post("/ai/tasks", json={"input": "내 등록 업무 알려줘"}, headers=EMP)
    assert r.status_code == 202
    task_id = r.json()["data"]["task_id"]
    evs = events(client, task_id, EMP)
    types = [e["type"] for e in evs]
    assert types[:2] == ["TOOL_START", "TOOL_END"] and types[-1] == "DONE"
    assert evs[0]["tool_call"]["name"] == "get_my_profile"
    t = wait_status(client, task_id, EMP, {"done"})
    assert t["result"]["evidence"][0]["source"] == "get_my_profile"
    assert t["turns"] == 2


def test_employee_cannot_execute_tool_error_is_returned_to_model(client):
    """직원에게는 execute_approved_plan이 노출되지 않는다. 오류가 ToolMessage로 돌아가고 작업은 정상 종료된다."""
    task_id = client.post("/ai/tasks", json={"input": "AI-A 이용권 신청하고 싶어요"}, headers=EMP).json()["data"]["task_id"]
    evs = events(client, task_id, EMP)
    names = [e["tool_call"]["name"] for e in evs if e["type"] == "TOOL_END"]
    assert names == ["create_action_plan", "execute_approved_plan"]
    exec_end = [e for e in evs if e["type"] == "TOOL_END"][1]
    assert exec_end["tool_call"]["error"] and "not_found" in exec_end["tool_call"]["output"]
    t = wait_status(client, task_id, EMP, {"done"})
    assert t["result"]["plan_id"].startswith("plan_") and evs[-1]["type"] == "DONE"


def test_seat_assign_by_asset_interrupts_then_resumes_and_executes(client):
    r = client.post("/ai/tasks", json={"input": "박서준 님 AI-A 이용권 배정해줘"}, headers=ASSET)
    task_id = r.json()["data"]["task_id"]
    evs = events(client, task_id, ASSET)
    types = [e["type"] for e in evs]
    assert types == ["TOOL_START", "TOOL_END", "APPROVAL_REQUIRED"], types
    card = evs[-1]["approval"]
    assert card["tool_name"] == "execute_approved_plan" and card["plan_id"].startswith("plan_")
    t = wait_status(client, task_id, ASSET, {"waiting_approval"})
    assert t["approval"]["tool_name"] == "execute_approved_plan"
    # 직원 역할은 승인 불가(본인 작업도 아님 → 403), 사유 없는 승인은 422
    assert client.post(f"/ai/tasks/{task_id}/approval", json={"approved": True, "reason": "ok"}, headers=EMP).status_code == 403
    assert client.post(f"/ai/tasks/{task_id}/approval", json={"approved": True, "reason": ""}, headers=ASSET).status_code == 422
    assert client.post(f"/ai/tasks/{task_id}/approval", json={"approved": True, "reason": "미배정 좌석 배정"}, headers=ASSET).status_code == 202
    evs2 = events(client, task_id, ASSET, after=len(evs))
    types2 = [e["type"] for e in evs2]
    assert types2[0] == "TOOL_START" and evs2[0]["tool_call"]["name"] == "execute_approved_plan" and types2[-1] == "DONE"
    t = wait_status(client, task_id, ASSET, {"done"})
    assert t["result"]["plan_id"] == card["plan_id"]
    assert json.loads(evs2[1]["tool_call"]["output"])["status"] == "executed"
    # 재승인은 conflict
    assert client.post(f"/ai/tasks/{task_id}/approval", json={"approved": True, "reason": "x"}, headers=ASSET).status_code == 409


def test_rejection_ends_without_execution(client):
    task_id = client.post("/ai/tasks", json={"input": "이용권 배정해줘"}, headers=ASSET).json()["data"]["task_id"]
    events(client, task_id, ASSET)
    wait_status(client, task_id, ASSET, {"waiting_approval"})
    client.post(f"/ai/tasks/{task_id}/approval", json={"approved": False, "reason": "예산 검토 먼저"}, headers=ASSET)
    t = wait_status(client, task_id, ASSET, {"done", "failed"})
    assert t["status"] == "done"
    assert all(tc["error"] or tc["name"] != "execute_approved_plan" for tc in t["tool_calls"])


def test_task_list_scoping(client):
    mine = client.get("/ai/tasks", params={"mine": True}, headers=EMP).json()["data"]
    assert mine and all(t["requester_id"] == "emp_mkt_01" for t in mine)
    assert client.get("/ai/tasks", params={"mine": False}, headers=EMP).status_code == 403
    assert client.get("/ai/tasks", params={"mine": False}, headers=ASSET).status_code == 200
