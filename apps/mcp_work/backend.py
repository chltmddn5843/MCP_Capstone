"""백엔드 REST 호출. MCP 서버는 DB에 닿지 않고 여기를 통해서만 업무 데이터를 읽고 바꾼다.

- 요청자의 Authorization, X-Trace-Id 헤더를 그대로 넘긴다. 권한 판단은 백엔드가 한다.
- 성공 봉투 {"data": ...}는 data만 꺼내 돌려준다.
- 오류 봉투 {"error": {...}}는 그대로 MCP 오류(ToolError)로 올린다.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TIMEOUT_SECONDS = float(os.environ.get("BACKEND_TIMEOUT_SECONDS", "10"))
FORWARD_HEADERS = {"authorization", "x-trace-id"}

# 테스트에서 httpx.ASGITransport(app=backend_app)로 바꿔 끼운다
_transport: httpx.AsyncBaseTransport | None = None


def use_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


def request_token() -> str | None:
    """요청자 토큰. HTTP로 연결하면 Authorization 헤더에서, stdio·인메모리 연결이면 MCP_DEV_TOKEN에서 읽는다."""
    auth = get_http_headers(include={"authorization"}).get("authorization")
    if auth:
        return auth
    dev = os.environ.get("MCP_DEV_TOKEN")
    return f"Bearer {dev}" if dev else None


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {k: v for k, v in get_http_headers(include=FORWARD_HEADERS).items() if k in FORWARD_HEADERS}
    token = request_token()
    if token:
        headers["authorization"] = token
    return {**headers, **(extra or {})}


def _error(code: str, message: str, details: dict | None = None) -> ToolError:
    return ToolError(json.dumps({"error": {"code": code, "message": message, "details": details}}, ensure_ascii=False))


async def call(method: str, path: str, *, params: dict | None = None, json_body: Any = None,
               headers: dict[str, str] | None = None) -> Any:
    """백엔드를 호출하고 봉투의 data를 돌려준다. 실패하면 오류 봉투를 담은 ToolError를 낸다."""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=TIMEOUT_SECONDS, transport=_transport) as client:
            response = await client.request(method, path, params=params, json=json_body, headers=_headers(headers))
    except httpx.TimeoutException as exc:
        raise _error("internal", "백엔드 응답이 늦습니다. 잠시 후 한 번만 다시 시도하세요.") from exc
    except httpx.HTTPError as exc:
        raise _error("internal", f"백엔드({BACKEND_URL})에 연결할 수 없습니다.") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        if isinstance(body, dict) and "error" in body:
            raise ToolError(json.dumps(body, ensure_ascii=False))
        if response.status_code in (404, 405):
            raise _error("not_found", f"백엔드에 {method} {path} API가 없습니다.", {"path": path})
        raise _error("internal", f"백엔드 오류 {response.status_code}", {"path": path})
    return body.get("data") if isinstance(body, dict) else body
