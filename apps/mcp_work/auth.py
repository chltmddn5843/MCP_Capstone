"""역할별 도구 노출. 요청자 토큰으로 역할을 읽고, ToolSpec.roles에 없는 도구는 tools/list에서 숨기고 호출도 막는다.

역할은 백엔드 GET /me로 확인한다(토큰 형식을 MCP가 해석하지 않는다). 토큰별로 MCP_ROLE_CACHE_SECONDS(기본 300초) 동안 캐시한다.
"""

from __future__ import annotations

import json
import os
import time

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from schemas.common import Role
from schemas.mcp_tools import ToolSpec

from apps.mcp_work import backend

# 토큰 → (역할, 확인 시각). 역할이 바뀌어도 이 시간이 지나면 백엔드에 다시 묻는다
ROLE_CACHE_SECONDS = float(os.environ.get("MCP_ROLE_CACHE_SECONDS", "300"))
_role_cache: dict[str, tuple[Role, float]] = {}


async def current_role() -> Role | None:
    """토큰이 없거나 백엔드가 거절하면 None. 그 경우 도구를 하나도 보여 주지 않는다."""
    token = backend.request_token()
    if not token:
        return None
    cached = _role_cache.get(token)
    if cached and time.monotonic() - cached[1] < ROLE_CACHE_SECONDS:
        return cached[0]
    try:
        me = await backend.call("GET", "/me")
    except ToolError:
        _role_cache.pop(token, None)
        return None
    role = Role(me["employee"]["role"])
    _role_cache[token] = (role, time.monotonic())
    return role


def clear_cache() -> None:
    _role_cache.clear()


class RoleFilter(Middleware):
    """specs: 도구 이름 → ToolSpec. 여기 없는 도구(등록 안 된 이름)는 건드리지 않는다."""

    def __init__(self, specs: dict[str, ToolSpec]):
        self.specs = specs

    def _allowed(self, name: str, role: Role | None) -> bool:
        spec = self.specs.get(name)
        return spec is None or (role is not None and role in spec.roles)

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        role = await current_role()
        return [t for t in tools if self._allowed(t.name, role)]

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        role = await current_role()
        if not self._allowed(name, role):
            allowed = [r.value for r in self.specs[name].roles]
            message = ("Authorization: Bearer <token> 헤더가 필요합니다" if role is None
                       else f"{role.value} 역할은 {name} 도구를 쓸 수 없습니다")
            code = "unauthorized" if role is None else "forbidden"
            raise ToolError(json.dumps({"error": {"code": code, "message": message,
                                                  "details": {"allowed_roles": allowed}}}, ensure_ascii=False))
        return await call_next(context)
