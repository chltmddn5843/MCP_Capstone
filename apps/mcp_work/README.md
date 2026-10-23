# 업무 MCP (담당: MCP)

포트 8010, Streamable HTTP. 설계 문서 7절.

## 해야 할 것
1. `schemas.mcp_tools.WORK_TOOLS`를 순회해 FastMCP 도구로 등록한다. 입력은 `spec.input_model`, 출력은 `spec.output_model`.
2. 요청 헤더의 토큰(`Authorization: Bearer dev.<employee_id>`)으로 역할을 읽고, `tools_for_role(role)`에 없는 도구는 `tools/list`에서 숨긴다.
3. 각 도구는 DB에 직접 닿지 않고 백엔드 REST(`spec.backend`)를 httpx로 부른다. 백엔드 오류 봉투 `{"error": {...}}`는 그대로 MCP 오류로 올린다.
4. Resource 6개, Prompt 6개는 `schemas.mcp_tools.RESOURCES / PROMPTS` 목록대로.

## 시작
```bash
uv sync
uv run python -m apps.mcp_work.server   # 만들 파일: server.py
npx @modelcontextprotocol/inspector     # tools/list에 역할별 도구가 보이면 1일차 완료
```

## 구현 상태
| 파일 | 내용 |
| --- | --- |
| `server.py` | 진입점. 도구·Resource·Prompt 등록, 역할 미들웨어 |
| `registry.py` | `ToolSpec` → FastMCP 도구. 입력 검증 → 어댑터 → `output_model` 검증 → structuredContent (문서 MCP도 사용) |
| `adapters.py` | 도구 22개의 백엔드 REST 호출과 응답 모양 맞추기 |
| `backend.py` | httpx 호출. `Authorization`, `X-Trace-Id` 전달. 오류 봉투 `{"error": {...}}`를 그대로 MCP 오류로 올림 |
| `auth.py` | 토큰 → 백엔드 `GET /me`로 역할 확인 → `tools/list`에서 숨기고 호출도 막음 |
| `resources.py`, `prompts.py` | Resource 6개, Prompt 6개 (`RESOURCES`, `PROMPTS` 목록과 같음) |

역할별로 보이는 도구 수: employee 11, admin 20, system 18. 토큰이 없으면 0개.

## 확인
```bash
uv run pytest tests/test_mcp_work.py          # 명세 등록, 역할별 노출, 오류 전달, F1~F4 흐름, Resource·Prompt
uv run uvicorn apps.backend.main:app --port 8000 &
uv run python -m apps.mcp_work.server         # Inspector에서 헤더 Authorization: Bearer dev.emp_asset_01
```
stdio·인메모리 연결처럼 헤더가 없을 때는 `MCP_DEV_TOKEN=dev.emp_asset_01`로 토큰을 준다(개발용).

## 남은 일
- ~~`request_confirmation` 라우트 없음~~ → `POST /confirmations` 추가됨 (2026-10-20).
- `approvers_required`: 백엔드 `POST /plans` 응답에 없어서 MCP가 백엔드 승인 규칙(`_decide`)대로 채운다. 지금 `model_change`는 `["asset"]`이다. 설계 문서 11절은 "자산관리 + 프로젝트 오너"인데 백엔드는 자산관리 한 명 승인으로 통과시키므로, 두 명 승인이 필요하면 백엔드 규칙을 먼저 바꾸고 백엔드가 승인자 목록을 내려 주게 한 뒤 MCP는 그 값을 그대로 쓴다.
- 역할 캐시: 토큰별 역할을 `MCP_ROLE_CACHE_SECONDS`(기본 300초) 동안 캐시한다. 역할을 바꾼 뒤 바로 확인하려면 0으로 둔다.
