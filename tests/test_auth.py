"""로그인: 사번·이메일 둘 다, 틀리면 같은 메시지, 5번 틀리면 잠금, JWT로 보호된 API 호출, 만료·위조 토큰 거절."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from apps.backend import auth
from apps.backend.main import app

client = TestClient(app)


def login(login_id: str, password: str):
    return client.post("/auth/login", json={"login_id": login_id, "password": password})


def test_login_by_id_or_email_and_use_token():
    r = login("emp_asset_01", "demo1234")
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    assert login("gwangcheol.choi@hanbit.example", "demo1234").status_code == 200
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()["data"]["employee"]
    assert me["id"] == "emp_asset_01" and me["role"] == "admin"


def test_wrong_password_same_message_then_lock():
    auth._fails.clear()
    bad = login("emp_cs_01", "nope").json()["error"]
    unknown = login("nobody", "nope").json()["error"]
    assert bad["code"] == unknown["code"] == "unauthorized" and bad["message"] == unknown["message"]
    for _ in range(4):
        login("emp_cs_01", "nope")
    r = login("emp_cs_01", "demo1234")                       # 5번 틀린 뒤엔 맞아도 잠김
    assert r.status_code == 401 and "잠겼" in r.json()["error"]["message"]
    auth._fails.clear()


def test_system_account_cannot_password_login():
    assert login("sys", "").status_code == 422
    assert login("sys", "anything").status_code == 401


def test_expired_and_forged_tokens_rejected():
    past = datetime.now(UTC) - timedelta(hours=2)
    expired = jwt.encode({"sub": "emp_mkt_01", "iat": past, "exp": past + timedelta(hours=1)}, auth.JWT_SECRET, algorithm="HS256")
    forged = jwt.encode({"sub": "emp_asset_01", "exp": datetime.now(UTC) + timedelta(hours=1)}, "wrong-secret-0123456789abcdefghij", algorithm="HS256")
    r1 = client.get("/me", headers={"Authorization": f"Bearer {expired}"})
    r2 = client.get("/me", headers={"Authorization": f"Bearer {forged}"})
    assert r1.status_code == r2.status_code == 401 and "만료" in r1.json()["error"]["message"]
