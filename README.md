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

### Docker로 팀원에게 공유

Docker Desktop이 실행된 상태에서 다음 명령을 실행합니다.

```bash
cp .env.example .env
# 외부에 공유할 때는 .env의 JWT_SECRET과 POSTGRES_PASSWORD를 반드시 변경합니다.
docker compose up -d --build
```

브라우저에서 `http://localhost:8080`으로 접속합니다. 같은 네트워크의 팀원에게는 실행 PC의 사설 IP와 포트를 공유합니다(예: `http://192.168.0.10:8080`). Backend·Agent 포트는 외부에 직접 공개하지 않고 Nginx를 통해서만 접근합니다. PostgreSQL은 DBeaver 사용을 위해 실행 PC의 `127.0.0.1:5432`에만 바인딩되며 팀원 LAN에는 공개되지 않습니다.

최초 기동 시 `app` 스키마와 시드 데이터가 자동으로 생성됩니다. 기존 볼륨을 지우고 처음부터 다시 시작할 때만 다음 명령을 사용합니다.

```bash
docker compose down -v
docker compose up -d --build
```

로그 확인:

```bash
docker compose logs -f web backend agent
```

### GitHub Push 자동 배포

현재 Mac에 GitHub Actions self-hosted runner를 설치하면 `main` 또는 `master` 브랜치에
push할 때마다 Docker Compose가 자동으로 재빌드·재기동됩니다.

1. GitHub 저장소의 **Settings → Actions → Runners → New self-hosted runner**에서 macOS 명령을 복사합니다.
2. 이 저장소 폴더가 아닌 GitHub가 안내하는 runner 전용 폴더에서 명령을 실행합니다.
3. runner 등록 시 라벨에 `docker`를 추가하고 runner 프로세스를 계속 실행합니다.
4. 저장소의 **Actions**에서 `Deploy Docker app`이 대기 없이 실행되는지 확인합니다.

runner가 꺼져 있거나 Mac이 잠자기 상태면 자동 배포되지 않습니다. Quick Tunnel도 같은 Mac의
프로세스이므로 Mac과 터널이 종료되면 외부 주소도 함께 끊깁니다.

자동 배포를 끄려면 GitHub Actions에서 workflow를 disable하거나 runner를 중지합니다.

에이전트는 `.env`의 `LLM_MODEL`로 모델을 고른다. 값은 DB `models.id`와 같은 `공급사:API 모델명` 키다
(예: `anthropic:claude-sonnet-5-5`, `anthropic:claude-opus-5-5`, `xai:grok-4.7`). 공급사별 API 키가 필요하다.
키가 없으면 `LLM_MODEL=fake`로 배선만 확인할 수 있다. `MCP_WORK_URL`이 비어 있으면 백엔드 REST를
직접 부르는 로컬 모드다. 설계는 `apps/agent_runtime/AGENT_DESIGN.md`.

## 로그인 (JWT)

- 화면: `http://localhost:5173/login` → 사번 또는 회사 이메일 + 비밀번호. 로그인하지 않으면 모든 화면이 로그인으로 보낸다.
- API: `POST /auth/login {login_id, password}` → `access_token` (HS256, 1시간). 이후 `Authorization: Bearer <token>`.
- 시드 계정 비밀번호는 `db/seed/seed.py`의 `DEMO_PASSWORD` (시스템 계정 `sys`는 로그인 불가). 5번 틀리면 5분 잠금.
- 개발 편의: `APP_ENV=dev`(기본)에서는 `/auth/dev-login`과 `dev.<직원id>` 토큰도 받는다. 로그인 화면의 "시연 계정" 버튼과 Slack 봇·테스트가 쓴다. **운영(`APP_ENV=prod`)에서는 막히고 `JWT_SECRET`이 필수다.**

```bash
curl -s localhost:8000/auth/login -H 'content-type: application/json' -d '{"login_id":"emp_asset_01","password":"<DEMO_PASSWORD>"}'
# 시드 직원: emp_asset_01(관리자) emp_mkt_01·emp_cs_01·emp_hrd_01(직원) sys(시스템)
```

## DB (PostgreSQL)

```bash
db/reset.sh        # postgres 컨테이너 기동 → db/schema.sql → 시드 적재 (DBeaver: localhost:5432 capstone/capstone, 스키마 app)
uv run pytest      # 테스트도 이 DB를 쓴다. 테스트마다 스키마·시드를 다시 넣는다
```
ERD 원본은 `db/schema.dbml`(dbdiagram.io), 점검 결과는 `db/README.md`.

## 구조

```
packages/schemas/   공유 Pydantic 스키마 = 명세 (common, entities, rest, mcp_tools, agent)
apps/backend/       FastAPI REST API (PostgreSQL 데이터·권한·승인·실행 규칙)
apps/agent_runtime/ LangGraph 에이전트: graph.py(StateGraph) · harness/(8요소) · prompts/ · tasks.py(작업·이벤트) · main.py(/ai/tasks API)
apps/admin_web/     Vue 3 관리자 콘솔 (화면은 backend만 호출, Vite `/api` 프록시 · nginx 이미지). apps/admin_web/README.md
apps/slack_bot/     Slack 봇 (수신) + 발신 메시지 빌더 send.py. apps/slack_bot/README.md
apps/admin_ui/      (구) Streamlit 화면. Vue로 대체 중이며 새 기능은 넣지 않는다
apps/mcp_work, apps/mcp_docs   MCP 서버 (schemas.mcp_tools.TOOLS를 순회해 등록)
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

- 로그인(JWT)·로그아웃, 만료·401이면 로그인 화면으로
- 제품·이용권·승인 대기 조회
- 비용 급증 알림 조회 및 예산 검토 요청 생성
- 처리 요청 승인·반려·실행
- 업데이트·제안·팀 활용·미지원 요청 조회
- 팀별 자동 발송 토글은 아직 백엔드 API(`PATCH /departments/{id}`)가 없어 읽기 전용이다.
- AI 비서는 Vite·nginx가 `/api/ai/*`를 에이전트로 직접 넘긴다. 레퍼런스대로 backend `/ai/tasks` 중계가 생기면 그 프록시 규칙만 지운다.

## 통신 구조

`docs/diagrams/`(PNG)와 `docs/architecture.drawio`. 요약: 브라우저 → admin_web(`/api/*`) → backend(JWT, 업무 규칙·DB) / agent(LLM·MCP). Slack 봇은 Socket Mode로 받아 backend·agent를 부르고, 제안 발송은 backend 발송함(`notify_outbox`)을 거친다.

## 팀원

| 이름   | 영역              |
| ------ | ----------------- |
| 최승우 | DB + 백엔드, 리드 |
| 이용주 | Agent + 프론트    |
| 유정연 | MCP               |
