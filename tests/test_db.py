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
