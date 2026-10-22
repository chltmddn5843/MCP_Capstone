"""backend /ai/tasks 중계: 헤더·쿼리·본문을 에이전트로 넘기고 응답(SSE 포함)을 그대로 돌려준다."""

import httpx
from fastapi.testclient import TestClient

from apps.backend import main

client = TestClient(main.app)
EMP = {"Authorization": "Bearer dev.emp_mkt_01"}


def test_relay_passes_request_and_response(monkeypatch):
    seen = []

    def agent(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith("/stream"):
            return httpx.Response(200, text="event: DONE\ndata: {}\n\n", headers={"content-type": "text/event-stream", "cache-control": "no-store"})
        return httpx.Response(202, json={"data": {"task_id": "t1"}})

    monkeypatch.setattr(main, "AGENT_TRANSPORT", httpx.MockTransport(agent))
    r = client.post("/ai/tasks", json={"input": "hi"}, headers=EMP)
    assert r.status_code == 202 and r.json()["data"]["task_id"] == "t1"
    assert seen[0].method == "POST" and seen[0].url.path == "/ai/tasks"
    assert seen[0].headers["authorization"] == EMP["Authorization"] and b'"hi"' in seen[0].content

    r = client.get("/ai/tasks/t1/stream", params={"after": 3}, headers=EMP)
    assert seen[1].url.params["after"] == "3"
    assert r.headers["content-type"].startswith("text/event-stream") and r.headers["cache-control"] == "no-store"
    assert r.text == "event: DONE\ndata: {}\n\n"


def test_relay_needs_login_and_reports_agent_down(monkeypatch):
    assert client.get("/ai/tasks").status_code == 401
    monkeypatch.setattr(main, "AGENT_URL", "http://127.0.0.1:9")  # 아무도 듣지 않는 포트
    r = client.get("/ai/tasks", headers=EMP)
    assert r.status_code == 503 and r.json()["error"]["code"] == "agent_unavailable"
