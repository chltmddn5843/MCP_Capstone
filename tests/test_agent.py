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


def test_employee_seat_request_is_executed_immediately(client):
    """직원 이용권 신청(낮은 위험)은 백엔드가 즉시 실행한다. 직원에게 실행 도구가 없어도 배정이 끝난다."""
    task_id = client.post("/ai/tasks", json={"input": "ChatGPT Enterprise 이용권 신청하고 싶어요"}, headers=EMP).json()["data"]["task_id"]
    evs = events(client, task_id, EMP)
    ends = [e for e in evs if e["type"] == "TOOL_END"]
    assert [e["tool_call"]["name"] for e in ends] == ["create_action_plan"] and evs[-1]["type"] == "DONE"
    assert json.loads(ends[0]["tool_call"]["output"])["status"] == "executed"
    t = wait_status(client, task_id, EMP, {"done"})
    assert "즉시 실행" in t["result"]["answer"] and t["result"]["plan_id"].startswith("plan_")


def test_reclaim_needs_approval_then_execute_interrupts_and_resumes(client):
    """중간 위험(회수·재배정): 조치안 → 담당자 승인(백엔드) → 에이전트 실행 요청 → 실행 도구 앞 interrupt → 승인 → 실행."""
    r = client.post("/ai/tasks", json={"input": "한도윤 님 휴직 중이라 이용권 회수해서 박지후 님에게 재배정해줘"}, headers=ASSET)
    task_id, thread_id = r.json()["data"]["task_id"], r.json()["data"]["thread_id"]
    evs = events(client, task_id, ASSET)
    assert [e["type"] for e in evs] == ["TOOL_START", "TOOL_END", "TOKEN", "DONE"]
    created = json.loads(evs[1]["tool_call"]["output"])
    plan_id = created["plan_id"]
    assert created["status"] == "pending_approval" and created["risk_level"] == "medium"
    # 담당자가 화면(백엔드)에서 승인
    from apps.backend.main import app as backend_app
    from fastapi.testclient import TestClient as BackendClient
    assert BackendClient(backend_app).post(f"/plans/{plan_id}/approve", json={"reason": "본인 반납 응답 확인"}, headers=ASSET).status_code == 200
    # 같은 대화에서 실행 요청 → 변경 도구 앞에서 멈춤
    r = client.post("/ai/tasks", json={"input": f"{plan_id} 실행해줘", "thread_id": thread_id}, headers=ASSET)
    task2 = r.json()["data"]["task_id"]
    evs2 = events(client, task2, ASSET)
    assert [e["type"] for e in evs2] == ["APPROVAL_REQUIRED"]
    card = evs2[-1]["approval"]
    assert card["tool_name"] == "execute_approved_plan" and card["plan_id"] == plan_id
    t = wait_status(client, task2, ASSET, {"waiting_approval"})
    assert client.post(f"/ai/tasks/{task2}/approval", json={"approved": True, "reason": "ok"}, headers=EMP).status_code == 403
    assert client.post(f"/ai/tasks/{task2}/approval", json={"approved": True, "reason": ""}, headers=ASSET).status_code == 422
    assert client.post(f"/ai/tasks/{task2}/approval", json={"approved": True, "reason": "재배정 실행"}, headers=ASSET).status_code == 202
    evs3 = events(client, task2, ASSET, after=len(evs2))
    assert evs3[0]["type"] == "TOOL_START" and evs3[0]["tool_call"]["name"] == "execute_approved_plan" and evs3[-1]["type"] == "DONE"
    assert json.loads(evs3[1]["tool_call"]["output"])["status"] == "executed"
    t = wait_status(client, task2, ASSET, {"done"})
    assert t["result"]["plan_id"] == plan_id
    assert client.post(f"/ai/tasks/{task2}/approval", json={"approved": True, "reason": "x"}, headers=ASSET).status_code == 409


def test_rejection_ends_without_execution(client):
    task_id = client.post("/ai/tasks", json={"input": "plan_002 실행해줘"}, headers=ASSET).json()["data"]["task_id"]
    evs = events(client, task_id, ASSET)
    assert evs[-1]["type"] == "APPROVAL_REQUIRED"
    wait_status(client, task_id, ASSET, {"waiting_approval"})
    client.post(f"/ai/tasks/{task_id}/approval", json={"approved": False, "reason": "예산 검토 먼저"}, headers=ASSET)
    t = wait_status(client, task_id, ASSET, {"done", "failed"})
    assert t["status"] == "done" and "거절" in t["result"]["answer"]
    assert all(tc["error"] or tc["name"] != "execute_approved_plan" for tc in t["tool_calls"])


def test_task_list_scoping(client):
    mine = client.get("/ai/tasks", params={"mine": True}, headers=EMP).json()["data"]
    assert mine and all(t["requester_id"] == "emp_mkt_01" for t in mine)
    assert client.get("/ai/tasks", params={"mine": False}, headers=EMP).status_code == 403
    assert client.get("/ai/tasks", params={"mine": False}, headers=ASSET).status_code == 200


def test_public_answer_has_no_internal_identifiers(client):
    """직원(또는 Slack 채널) 답변에는 도구 이름·id·근거 줄이 없다. 참고 데이터는 evidence에 남는다."""
    task_id = client.post("/ai/tasks", json={"input": "AI-A 이용권 신청하고 싶어요", "channel": "slack"}, headers=EMP).json()["data"]["task_id"]
    events(client, task_id, EMP)
    t = wait_status(client, task_id, EMP, {"done"})
    ans = t["result"]["answer"]
    assert "근거" not in ans and "create_action_plan" not in ans and "plan_" not in ans and "emp_" not in ans, ans
    assert t["result"]["evidence"] and t["result"]["plan_id"].startswith("plan_")  # 구조화된 참고 데이터는 유지


def test_admin_web_answer_keeps_evidence_line(client):
    task_id = client.post("/ai/tasks", json={"input": "내 등록 업무 알려줘", "channel": "admin_ui"}, headers=ASSET).json()["data"]["task_id"]
    events(client, task_id, ASSET)
    t = wait_status(client, task_id, ASSET, {"done"})
    assert "get_my_profile" in t["result"]["answer"]  # 관리자 웹에서는 상세 유지 (스크립트 모델은 도구 이름을 답에 넣는다)


def test_recommend_asks_missing_conditions_once_then_continues(client):
    """모델 추천인데 F2 조건이 부족하면 도구 없이 질문 하나로 끝내고, 같은 대화에서 답하면 루프로 진행한다."""
    r = client.post("/ai/tasks", json={"input": "고객 문의 분류에 어떤 모델 쓰면 좋을까요?"}, headers=EMP).json()["data"]
    t = wait_status(client, r["task_id"], EMP, {"done"})
    assert not t["tool_calls"] and "하루 건수" in t["result"]["answer"] and "허용 응답 시간" in t["result"]["answer"]
    # 일부만 답해도 두 번째는 묻지 않고 진행한다 (스크립트 모델은 get_my_profile을 부른다)
    r2 = client.post("/ai/tasks", json={"input": "하루 1,000건 정도예요", "thread_id": r["thread_id"]}, headers=EMP).json()["data"]
    t2 = wait_status(client, r2["task_id"], EMP, {"done"})
    assert [c["name"] for c in t2["tool_calls"]] == ["get_my_profile"]


SYS = {"Authorization": "Bearer dev.sys"}


@pytest.mark.parametrize("kind,target,column", [("plan", "plan_002", "ai_opinion"), ("anomaly", "anm_001", "ai_note")])
def test_system_task_saves_ai_note(client, kind, target, column):
    """배치가 맡긴 시스템 작업(승인 대기 의견·경보 조사)이 save_ai_note로 결과를 백엔드에 남긴다."""
    from apps.backend import db
    text = f"[작업] 검토 후 save_ai_note(target_type={kind}, target_id={target})로 남긴다."
    r = client.post("/ai/tasks", json={"input": text, "channel": "system"}, headers=SYS).json()["data"]
    t = wait_status(client, r["task_id"], SYS, {"done"})
    assert [c["name"] for c in t["tool_calls"]] == ["save_ai_note"] and not t["tool_calls"][0]["error"]
    table = "action_plans" if kind == "plan" else "anomalies"
    assert "자동 검토 의견" in db.one(f"SELECT {column} FROM {table} WHERE id = :id", id=target)[column]
