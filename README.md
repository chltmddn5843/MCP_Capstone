# 기업 AI 활용·운영 최적화 에이전트 (Capstone MVP)

설계 문서: `docs/설계문서.md` (v2, 2026-10-21) · 에이전트 설계: `apps/agent_runtime/AGENT_DESIGN.md` · 개발 규칙: `CONTRIBUTING.md`

## 시작하기

```bash
uv sync                       # 전부 설치 (테스트 포함). pip라면: pip install -e ".[dev]"
cp .env.example .env          # OPENAI_API_KEY 채우기 (키 없으면 LLM_MODEL=fake)
scripts/run_all.sh            # 백엔드·MCP 2개·에이전트·관리자 화면을 한 번에. Ctrl+C로 종료
```

통합 실행은 `apps/admin_web`의 Vue 관리자 화면을 사용한다. `scripts/run_all.sh`가
필요하면 Node 의존성을 설치하고 백엔드·MCP·에이전트·Vite를 함께 실행한다.

**관리자 화면은 백엔드(8000)가 떠 있어야 동작한다.** 따로 띄우려면:

```bash
uv run uvicorn apps.backend.main:app --reload --port 8000         # http://localhost:8000/docs
uv run uvicorn apps.agent_runtime.main:app --reload --port 8002   # http://localhost:8002/docs
cd apps/admin_web && npm install && npm run dev                   # http://localhost:5173 (Vue 관리자 콘솔)
uv run pytest                 # 계약 테스트 + 에이전트 테스트 (키 불필요)
uv run python specs/export.py # specs/*.json 갱신
```

에이전트는 `.env`의 `LLM_MODEL`로 모델을 고른다. Anthropic은 `anthropic:claude-opus-4-7`,
OpenAI는 `openai:gpt-5.2`, xAI는 `xai:grok-4.7` 형식을 사용하며 각각의 API 키가 필요하다.
키가 없으면 `LLM_MODEL=fake`로 배선만 확인할 수 있다. `MCP_WORK_URL`이 비어 있으면 백엔드 REST를
직접 부르는 로컬 모드다. 설계는 `apps/agent_runtime/AGENT_DESIGN.md`.

## 관리자 화면 인증 (개발용)

현재 Vue 관리자 화면에는 별도 로그인 페이지가 없다. 최초 접속 시 `emp_asset_01`로
`/auth/dev-login`을 자동 호출하고, 발급된 토큰을 브라우저 `localStorage`에 저장한다.
실제 로그인 화면은 후속 작업이다.

## 토큰 발급 (MVP 인증)

```bash
curl -s localhost:8000/auth/dev-login -H 'content-type: application/json' -d '{"employee_id":"emp_asset_01"}'
# 시드 직원: emp_hrd_01(HRD) emp_mkt_01(직원) emp_cs_01(직원) emp_asset_01(자산관리) emp_approver_01(승인자) sys(시스템)
curl -s localhost:8000/inventory -H 'Authorization: Bearer dev.emp_asset_01'
```

## 구조

```
packages/schemas/   공유 Pydantic 스키마 = 명세 (common, entities, rest, mcp_tools, agent)
apps/backend/       FastAPI REST API (PostgreSQL 데이터·권한·승인·실행 규칙)
apps/agent_runtime/ LangGraph 에이전트: graph.py(StateGraph) · harness/(8요소) · prompts/ · tasks.py(작업·이벤트) · main.py(/ai/tasks API)
apps/admin_web/     Vue 3 관리자 콘솔 (화면은 backend만 호출, Vite `/api` 프록시 · nginx 이미지). apps/admin_web/README.md
apps/slack_bot/     Slack 봇 (수신) + 발신 메시지 빌더 send.py. apps/slack_bot/README.md
apps/admin_ui/      (구) Streamlit 화면. Vue로 대체 중이며 새 기능은 넣지 않는다
apps/mcp_work, apps/mcp_docs   MCP 서버 (schemas.mcp_tools.TOOLS를 순회해 등록)
apps/slack_bot, apps/admin_web  접점
apps/mock_vendor, jobs/, db/   Mock 벤더, 배치, 스키마·시드
specs/              export.py가 생성하는 openapi·mcp_tools JSON
tests/              계약 테스트
```

## 포트

| 서비스          | 포트 |
| --------------- | ---- |
| backend         | 8000 |
| mock_vendor     | 8001 |
| agent_runtime   | 8002 |
| mcp_work        | 8010 |
| mcp_docs        | 8011 |
| admin_web (Vue) | 5173 |

## 현재 연결 범위

Vue 화면은 `apps/admin_web/src/api.js`를 통해 백엔드 REST API를 호출한다.

- 자동 개발 로그인, 제품·이용권·승인 대기 조회
- 비용 급증 알림 조회 및 예산 검토 요청 생성
- 처리 요청 승인·반려·실행
- 업데이트·제안·팀 활용·미지원 요청 조회
- 팀별 자동 발송 토글은 아직 백엔드 API가 없어 읽기 전용이다.

## 팀원

| 이름   | 영역              |
| ------ | ----------------- |
| 최승우 | DB + 백엔드, 리드 |
| 이용주 | Agent + 프론트    |
| 유정연 | MCP               |
