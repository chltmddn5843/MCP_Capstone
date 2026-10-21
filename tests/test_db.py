"""DB 전환 확인: API 호출이 실제 테이블을 바꾸고, 제약이 잘못된 상태를 막는다."""

from fastapi.testclient import TestClient

from apps.backend import db
from apps.backend.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev.emp_asset_01"}


def unassigned() -> int:
    inv = client.get("/inventory", params={"contract_id": "ctr_ai_a_2026"}, headers=ADMIN).json()["data"][0]
    return inv["unassigned"]


def test_reclaim_frees_seat_and_writes_audit():
    before = unassigned()
    assert client.post("/plans/plan_002/approve", json={"reason": "본인 반납 응답"}, headers=ADMIN).status_code == 200
    r = client.post("/plans/plan_002/execute", headers={**ADMIN, "Idempotency-Key": "db-k1"})
    assert r.status_code == 200 and r.json()["data"]["plan"]["status"] == "executed"
    assert unassigned() == before + 1
    actions = [a["action"] for a in db.rows("SELECT action FROM audit_log WHERE target = 'plan_002' ORDER BY created_at")]
    assert actions[-2:] == ["plan.approve", "plan.execute"]
    # 다른 키로 다시 실행하면 거절, 같은 키는 같은 결과
    assert client.post("/plans/plan_002/execute", headers={**ADMIN, "Idempotency-Key": "db-k2"}).status_code == 409
    assert client.post("/plans/plan_002/execute", headers={**ADMIN, "Idempotency-Key": "db-k1"}).json()["data"] == r.json()["data"]


def test_second_decision_conflicts():
    assert client.post("/plans/plan_002/reject", json={"reason": "아직 사용 중"}, headers=ADMIN).status_code == 200
    assert client.post("/plans/plan_002/approve", json={"reason": "번복"}, headers=ADMIN).status_code == 409


SYS = {"Authorization": "Bearer dev.sys"}
WORK_HOUR = "2026-10-20T01:00:00Z"   # 월요일 10:00 KST
NIGHT = "2026-10-20T12:00:00Z"       # 월요일 21:00 KST


def team_suggestion(dept: str) -> str:
    body = {"update_id": "upd_ai_a_doc_compare", "target_type": "team", "target_id": dept, "relevance": "근거", "body": "제안"}
    return client.post("/suggestions", json=body, headers=SYS).json()["data"]["id"]


def run(job: str, now: str) -> dict:
    return client.post(f"/internal/jobs/{job}/run", params={"now": now}, headers=SYS).json()["data"]["result"]


def test_send_policy_hours_cap_and_switch():
    hrd = team_suggestion("dept_hrd")
    assert "deferred" in run("send_suggestions", NIGHT)                       # 업무 시간 밖이면 미룸
    prod = team_suggestion("dept_prod")                                       # 생산관리는 자동 발송 꺼짐(시드)
    extra = team_suggestion("dept_mkt")                                       # 마케팅은 이미 이번 주 1건 → 1건 더 가능
    extra2 = team_suggestion("dept_mkt")
    r = run("send_suggestions", WORK_HOUR)
    sent = {x["suggestion_id"] for x in r["sent"]}
    held = {x["suggestion_id"]: x["reason"] for x in r["held"]}
    assert hrd in sent and extra in sent
    assert "꺼짐" in held[prod] and "상한" in held[extra2]
    outbox = client.get("/notify-outbox", headers=ADMIN).json()["data"]
    assert {o["suggestion_id"] for o in outbox} == sent
    assert client.get("/review-runs", headers=ADMIN).json()["data"]


def test_two_irrelevant_holds_team():
    cs = [g["id"] for g in db.rows("SELECT id FROM employees WHERE dept_id = 'dept_cs' AND role = 'employee' ORDER BY id")]
    sid = team_suggestion("dept_cs")
    for e in cs[-2:]:
        r = client.post(f"/suggestions/{sid}/feedback", json={"reaction": "irrelevant"}, headers={"Authorization": f"Bearer dev.{e}"})
    assert r.json()["data"]["team_hold_until"]                                # 2회 연속 → 4주 보류
    held = run("send_suggestions", WORK_HOUR)["held"]
    assert any(x["dept_id"] == "dept_cs" and "보류" in x["reason"] for x in held)


def test_threshold_job_finds_quote_summary_spike():
    with db.tx() as c:  # 시드 경보를 지우고 배치가 다시 찾는지 본다
        c.execute(db.text("DELETE FROM anomalies"))
    made = run("check_thresholds", "2026-10-20T00:00:00Z")["new_anomalies"]
    rows = client.get("/anomalies", headers=ADMIN).json()["data"]
    assert len(made) == 1 and rows[0]["scope_id"] == "prj_quote_summary" and rows[0]["ratio"] > 3
    assert run("check_thresholds", "2026-10-20T00:00:00Z")["new_anomalies"] == []   # 같은 날 중복 경보 없음
