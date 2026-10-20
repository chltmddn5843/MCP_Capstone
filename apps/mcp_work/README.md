# 업무 MCP (담당: MCP)

포트 8010, Streamable HTTP. 설계 문서 7절.

## 해야 할 것
1. `schemas.mcp_tools.WORK_TOOLS`를 순회해 FastMCP 도구로 등록한다. 입력은 `spec.input_model`, 출력은 `spec.output_model`.
2. 요청 헤더의 토큰(`Authorization: Bearer dev.<employee_id>`)으로 역할을 읽고, `tools_for_role(role)`에 없는 도구는 `tools/list`에서 숨긴다.
3. 각 도구는 DB에 직접 닿지 않고 백엔드 REST(`spec.backend`)를 httpx로 부른다. 백엔드 오류 봉투 `{"error": {...}}`는 그대로 MCP 오류로 올린다.
4. Resource 6개, Prompt 6개는 `schemas.mcp_tools.RESOURCES / PROMPTS` 목록대로.

## 시작
```bash
uv sync --extra mcp
uv run python -m apps.mcp_work.server   # 만들 파일: server.py
npx @modelcontextprotocol/inspector     # tools/list에 역할별 도구가 보이면 1일차 완료
```
