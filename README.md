# 기업 AI 활용·운영 최적화 에이전트 (Capstone MVP)

설계 문서: `기업 AI 활용·운영 최적화 에이전트 설계 문서.md` · 개발 규칙: `CONTRIBUTING.md`

## 시작하기
```bash
uv sync --all-extras          # 또는: pip install -e ".[dev]"
cp .env.example .env
uv run uvicorn apps.backend.main:app --reload --port 8000         # http://localhost:8000/docs
uv run uvicorn apps.agent_runtime.main:app --reload --port 8002   # http://localhost:8002/docs
uv run pytest                 # 계약 테스트
uv run python specs/export.py # specs/*.json 갱신
```

## 토큰 발급 (MVP 인증)
```bash
curl -s localhost:8000/auth/dev-login -H 'content-type: application/json' -d '{"employee_id":"emp_asset_01"}'
# 시드 직원: emp_hrd_01(HRD) emp_mkt_01(직원) emp_cs_01(직원) emp_asset_01(자산관리) emp_approver_01(승인자) sys(시스템)
curl -s localhost:8000/inventory -H 'Authorization: Bearer dev.emp_asset_01'
```

## 구조
```
packages/schemas/   공유 Pydantic 스키마 = 명세 (common, entities, rest, mcp_tools, agent)
apps/backend/       REST API (현재 스텁: 고정 데이터, 권한·승인·실행 규칙은 동작)
apps/agent_runtime/ 에이전트 실행·SSE 이벤트 (현재 스텁)
apps/mcp_work, apps/mcp_docs   MCP 서버 (schemas.mcp_tools.TOOLS를 순회해 등록)
apps/slack_bot, apps/admin_ui  접점
apps/mock_vendor, jobs/, db/   Mock 벤더, 배치, 스키마·시드
specs/              export.py가 생성하는 openapi·mcp_tools JSON
tests/              계약 테스트
```

## 포트
| 서비스 | 포트 |
| --- | --- |
| backend | 8000 |
| mock_vendor | 8001 |
| agent_runtime | 8002 |
| mcp_work | 8010 |
| mcp_docs | 8011 |
| admin_ui (Streamlit) | 8501 |

## 팀원
| 이름 | 영역 |
| --- | --- |
| 이용주 | Agent + 프론트, 리드 |
