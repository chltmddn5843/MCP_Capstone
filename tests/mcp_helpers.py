"""MCP 테스트 공용 도구. 백엔드 스텁을 같은 프로세스에서 띄워(ASGI) MCP 서버가 실제 REST를 부르게 한다."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
from fastmcp import Client

from apps.backend.main import app as backend_app
from apps.mcp_work import auth, backend

TRANSPORT = httpx.ASGITransport(app=backend_app)
TOKENS = {"employee": "dev.emp_mkt_01", "cs": "dev.emp_cs_01", "hrd": "dev.emp_hrd_01",
          "asset": "dev.emp_asset_01", "approver": "dev.emp_approver_01", "system": "dev.sys"}


@asynccontextmanager
async def connect(server, monkeypatch, who: str | None):
    """who 역할의 토큰으로 MCP 서버에 인메모리 연결한다. None이면 토큰 없이 연결한다."""
    backend.use_transport(TRANSPORT)
    auth.clear_cache()
    if who:
        monkeypatch.setenv("MCP_DEV_TOKEN", TOKENS[who])
    else:
        monkeypatch.delenv("MCP_DEV_TOKEN", raising=False)
    async with Client(server) as client:
        yield client


def error_of(result) -> dict:
    """도구 오류 응답의 {"error": {...}} 봉투를 꺼낸다."""
    assert result.is_error, result
    return json.loads(result.content[0].text)["error"]


async def backend_post(path: str, who: str, body: dict | None = None, headers: dict | None = None) -> dict:
    """사람이 화면에서 하는 일(승인 등)은 MCP가 아니라 백엔드를 직접 부른다."""
    async with httpx.AsyncClient(transport=TRANSPORT, base_url="http://backend") as client:
        r = await client.post(path, json=body, headers={"Authorization": f"Bearer {TOKENS[who]}", **(headers or {})})
        return r.json()
