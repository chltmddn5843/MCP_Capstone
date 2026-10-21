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


def test_threshold_job_finds_seeded_spikes():
    with db.tx() as c:  # 시드 경보를 지우고 배치가 다시 찾는지 본다
        c.execute(db.text("DELETE FROM anomalies"))
    made = run("check_thresholds", "2026-10-20T00:00:00Z")["new_anomalies"]
    rows = client.get("/anomalies", headers=ADMIN).json()["data"]
    # 시드의 급증 두 건: 견적서 요약(긴 PDF)·캠페인 카피(요청 4배, 페르소나 서연 시나리오)
    assert len(made) == 2 and {r["scope_id"] for r in rows} == {"prj_quote_summary", "prj_mkt_copy"} and all(r["ratio"] > 3 for r in rows)
    assert run("check_thresholds", "2026-10-20T00:00:00Z")["new_anomalies"] == []   # 같은 날 중복 경보 없음


def tools_of(emp: str) -> set[str]:
    return {t["id"] for t in client.get(f"/employees/{emp}/assets", headers=ADMIN).json()["data"]["available_tools"]}


def assign(emp: str):
    return client.post("/plans", headers=ADMIN, json={"type": "seat_assign", "items": [{"employee_id": emp, "contract_id": "ctr_ai_a_2026"}],
                                                      "rationale": "t", "evidence": []})


def test_grant_and_revoke_change_usable_tools():
    """부여하면 그 직원의 실제 사용 가능 도구에 생기고, 회수하면 사라진다. API 도구는 팀 프로젝트가 있을 때만."""
    assert "tool_ai_a" not in tools_of("emp_mkt_01")
    assert "tool_ai_b" in tools_of("emp_cs_01") and "tool_ai_b" not in tools_of("emp_hrd_01")  # HRD팀은 Claude API 프로젝트가 없다
    plan = assign("emp_mkt_01").json()["data"]
    assert plan["status"] == "pending_approval"  # v2.1: 배정도 관리자 승인 뒤 실행
    client.post(f"/plans/{plan['id']}/approve", headers=ADMIN, json={"reason": "t"})
    assert client.post(f"/plans/{plan['id']}/execute", headers={**ADMIN, "Idempotency-Key": "as1"}).status_code == 200
    assert "tool_ai_a" in tools_of("emp_mkt_01")
    plan = client.post("/plans", headers=ADMIN, json={"type": "seat_reclaim", "items": [{"employee_id": "emp_mkt_01", "contract_id": "ctr_ai_a_2026"}],
                                                      "rationale": "t", "evidence": []}).json()["data"]
    client.post(f"/plans/{plan['id']}/approve", headers=ADMIN, json={"reason": "t"})
    assert client.post(f"/plans/{plan['id']}/execute", headers={**ADMIN, "Idempotency-Key": "rv1"}).status_code == 200
    assert "tool_ai_a" not in tools_of("emp_mkt_01")


def test_assign_revalidates_before_execute():
    """중복 배정·휴직자·좌석 초과는 승인 대기에 들어가기 전에 막고(409) 조치안을 failed로 남긴다. 절감 기록은 생기지 않는다."""
    savings = db.one("SELECT count(*) AS n FROM savings_ledger")["n"]
    for emp, why in [("emp_gen_002", "이미"), ("emp_gen_007", "on_leave")]:
        r = assign(emp)
        assert r.status_code == 409 and why in r.json()["error"]["message"]
        assert db.one("SELECT status FROM action_plans WHERE id = :id", id=r.json()["error"]["details"]["plan_id"])["status"] == "failed"
    with db.tx() as c:  # 좌석을 꽉 채운 상태로 만든다 (구매 수 = 배정 수)
        c.execute(db.text("UPDATE contracts SET seats_purchased = 58 WHERE id = 'ctr_ai_a_2026'"))
    r = assign("emp_mkt_01")
    assert r.status_code == 409 and "남은 좌석 0석" in r.json()["error"]["message"]
    assert db.one("SELECT count(*) AS n FROM savings_ledger")["n"] == savings


SEED_CHECKS = {  # 시드 일관성: 모두 0건이어야 한다
    "need 부서 ≠ 직원 부서": "SELECT count(*) AS n FROM unmet_needs n JOIN employees e ON e.id = n.employee_id WHERE n.dept_id <> e.dept_id",
    "휴직자 좌석에 on_leave 표시 없음": "SELECT count(*) AS n FROM seat_assignments s JOIN employees e ON e.id = s.employee_id"
                              " WHERE e.status <> 'active' AND s.status = 'assigned' AND s.flag IS DISTINCT FROM 'on_leave'",
    "배정일 < 입사일": "SELECT count(*) AS n FROM seat_assignments s JOIN employees e ON e.id = s.employee_id WHERE s.assigned_at::date < e.hire_date",
    "좌석 초과": "SELECT count(*) AS n FROM (SELECT 1 FROM contracts c JOIN seat_assignments s ON s.contract_id = c.id AND s.status = 'assigned'"
             " GROUP BY c.id, c.seats_purchased HAVING count(*) > c.seats_purchased) x",
    "미실행 조치안의 절감": "SELECT count(*) AS n FROM savings_ledger v JOIN action_plans p ON p.id = v.plan_id WHERE p.status <> 'executed'",
    "사용량 모델 ≠ 계약 제품": "SELECT count(*) AS n FROM usage_records u JOIN models m ON m.id = u.model_id JOIN contracts c ON c.id = u.contract_id WHERE m.tool_id <> c.tool_id",
    "미승인 모델 쓰는 프로젝트": "SELECT count(*) AS n FROM projects p JOIN models m ON m.id = p.model_id WHERE NOT m.approved",
}


def test_seed_is_consistent():
    assert {k: db.one(q)["n"] for k, q in SEED_CHECKS.items()} == dict.fromkeys(SEED_CHECKS, 0)


def test_model_change_execute_applies_and_revalidates():
    """모델 변경은 실행하면 프로젝트 모델이 실제로 바뀌고, 이미 바뀐 뒤 같은 요청은 stale(failed)로 멈춘다."""
    item = {"project_id": "prj_faq", "from_model_id": "anthropic:claude-sonnet-5-5", "to_model_id": "anthropic:claude-haiku-5-5", "environment": "test"}

    def run(key):
        p = client.post("/plans", headers=ADMIN, json={"type": "model_change", "items": [item], "rationale": "t", "evidence": []}).json()["data"]
        client.post(f"/plans/{p['id']}/approve", headers=ADMIN, json={"reason": "t"})
        return client.post(f"/plans/{p['id']}/execute", headers={**ADMIN, "Idempotency-Key": key})

    assert run("mc1").status_code == 200
    assert db.one("SELECT model_id FROM projects WHERE id = 'prj_faq'")["model_id"] == "anthropic:claude-haiku-5-5"
    r = run("mc2")
    assert r.status_code == 409 and "이미" in r.json()["error"]["message"]
