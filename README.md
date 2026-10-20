# 기업 AI 활용·운영 최적화 에이전트 (Capstone MVP)

설계 문서: `docs/설계문서.md` (v2, 2026-10-21) · 에이전트 설계: `apps/agent_runtime/AGENT_DESIGN.md` · 개발 규칙: `CONTRIBUTING.md`

## 시작하기
```bash
uv sync                       # 전부 설치 (테스트 포함). pip라면: pip install -e ".[dev]"
cp .env.example .env          # OPENAI_API_KEY 채우기 (키 없으면 LLM_MODEL=fake)
scripts/run_all.sh            # 백엔드·MCP 2개·에이전트·관리자 화면을 한 번에. Ctrl+C로 종료
```

**관리자 화면은 백엔드(8000)와 에이전트(8002)가 떠 있어야 동작한다.** 따로 띄우려면:
```bash
uv run uvicorn apps.backend.main:app --reload --port 8000         # http://localhost:8000/docs
uv run uvicorn apps.agent_runtime.main:app --reload --port 8002   # http://localhost:8002/docs
uv run streamlit run apps/admin_ui/app.py                         # http://localhost:8501
uv run pytest                 # 계약 테스트 + 에이전트 테스트 (키 불필요)
uv run python specs/export.py # specs/*.json 갱신
```

에이전트는 `.env`의 `LLM_MODEL`로 모델을 고른다. `ANTHROPIC_API_KEY`(또는 `OPENAI_API_KEY` + `LLM_MODEL=openai:...`)가 있어야 실제 모델이 돌고, 키가 없으면 `LLM_MODEL=fake`로 배선만 확인할 수 있다. `MCP_WORK_URL`이 비어 있으면 백엔드 REST를 직접 부르는 로컬 모드다. 설계는 `apps/agent_runtime/AGENT_DESIGN.md`.

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
apps/agent_runtime/ LangGraph 에이전트: graph.py(StateGraph) · harness/(8요소) · prompts/ · tasks.py(작업·이벤트) · main.py(/ai/tasks API)
apps/admin_ui/      Streamlit 화면. 로그인 역할별로 다른 화면 (직원: AI 비서·내 업무 / HRD: 활용 현황·공지 승인 / 자산관리: 이용권·비용 경보·도입 검토·승인함 / 승인자: 승인함). 용어는 labels.py
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
