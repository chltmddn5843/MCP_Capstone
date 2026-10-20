"""업무 MCP (설계 문서 7절). 포트 8010, Streamable HTTP.

- schemas.mcp_tools.WORK_TOOLS를 순회해 도구로 등록한다. 입력·출력은 spec.input_model / spec.output_model.
- 요청 토큰으로 역할을 읽어 tools_for_role(role)에 없는 도구는 tools/list에서 숨기고 호출도 막는다.
- 도구는 DB에 닿지 않고 백엔드 REST(spec.backend)를 httpx로 부른다. 오류 봉투는 그대로 MCP 오류로 올린다.
- Resource 6개, Prompt 6개는 schemas.mcp_tools.RESOURCES / PROMPTS 목록대로 둔다.

실행: uv run python -m apps.mcp_work.server   →  http://localhost:8010/mcp
"""

from __future__ import annotations

import os

from fastmcp import FastMCP
from schemas.mcp_tools import WORK_TOOLS

from apps.mcp_work.adapters import ADAPTERS
from apps.mcp_work.auth import RoleFilter
from apps.mcp_work.prompts import register_prompts
from apps.mcp_work.registry import register_specs
from apps.mcp_work.resources import register_resources


def build_server() -> FastMCP:
    mcp = FastMCP("mcp-work", instructions=(
        "기업 AI 활용·운영 최적화 업무 도구. 실행이 필요한 일은 create_action_plan으로 조치안만 만들고, "
        "승인된 뒤에만 execute_approved_plan을 부른다. 도구 오류는 {\"error\": {code, message, details}} 형식이다."))
    register_specs(mcp, WORK_TOOLS, ADAPTERS)
    register_resources(mcp)
    register_prompts(mcp)
    mcp.add_middleware(RoleFilter({s.name: s for s in WORK_TOOLS}))
    return mcp


mcp = build_server()

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("MCP_WORK_PORT", "8010")),
            path="/mcp", show_banner=False)
