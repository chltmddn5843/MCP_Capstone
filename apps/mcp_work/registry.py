"""ToolSpec 목록을 FastMCP 도구로 바꾼다. 업무 MCP와 문서 MCP가 함께 쓴다.

입력 스키마는 spec.input_model, 출력 스키마는 spec.output_model에서 만든다.
도구 실행 = 입력 검증 → 어댑터(백엔드 호출) → 출력 모델로 검증 → structuredContent로 반환.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool, ToolResult
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, ValidationError
from schemas.mcp_tools import ToolSpec


class SpecTool(Tool):
    """schemas의 ToolSpec 하나를 감싼 도구."""

    spec: ToolSpec
    handler: Callable[[BaseModel], Awaitable[dict]]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            params = self.spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolError(json.dumps({"error": {"code": "invalid", "message": "입력 검증 실패",
                                                  "details": {"errors": exc.errors(include_url=False)}}},
                                       ensure_ascii=False, default=str)) from exc
        raw = await self.handler(params)
        out = self.spec.output_model.model_validate(raw).model_dump(mode="json")
        return ToolResult(content=json.dumps(out, ensure_ascii=False), structured_content=out)


def register_specs(mcp: FastMCP, specs: list[ToolSpec], handlers: dict[str, Callable]) -> None:
    missing = [s.name for s in specs if s.name not in handlers]
    if missing:
        raise RuntimeError(f"어댑터가 없는 도구: {missing}")
    for spec in specs:
        mcp.add_tool(SpecTool(
            name=spec.name,
            description=spec.description,
            parameters=spec.input_model.model_json_schema(),
            output_schema=spec.output_model.model_json_schema(),
            annotations=ToolAnnotations(read_only_hint=spec.read_only, destructive_hint=spec.destructive,
                                        idempotent_hint=spec.idempotent),
            meta={"roles": [r.value for r in spec.roles], "backend": spec.backend, "features": spec.features},
            tags=set(spec.features),
            spec=spec,
            handler=handlers[spec.name],
        ))
