# admin_web — 관리자 웹 (Vue 3 + Vite)

와이어프레임(https://claude.ai/artifact/6nPHyWDmv1SGHgmiQZ4EkW)을 옮긴 관리자 화면. **실제 백엔드·에이전트에 연결돼 있다.** 화면은 `src/api.js`만 부르고, 그 안에서 백엔드 응답(`packages/schemas`)을 화면 모양으로 바꾼다.

```bash
cd apps/admin_web
npm install
npm run dev        # http://localhost:5173  (백엔드 8000, 에이전트 8002가 떠 있어야 한다 → scripts/run_all.sh)
npm run build      # dist/
```

| 경로 | 화면 | 기능 |
| --- | --- | --- |
| `/` | 홈 · 지금 확인할 일 | 전체 |
| `/inbox` | 승인 대기 · AI 의견 · **AI 비서 처리 확인** | 처리 요청 |
| `/licenses` | 구독·이용권 | F4 |
| `/cost` | 비용·사용량 · 급증 알림 · AI 조사 | F3 |
| `/suggestions` | 자동 제안 기록 | F1 |
| `/needs` | 미지원 요청 · 팀 활용 | F5 |
| `/assistant` | **AI 비서에게 묻기** (진행 스트림, 내 요청) | 전체 |

## 구조
- `src/request.js` — fetch 공통(`/api/*`), 토큰(dev-login 자동, JWT 로그인 화면은 후속), SSE 스트리밍(`streamTask`), 에이전트 작업 API.
- `src/api.js` — 화면별 데이터 함수. 함수 이름·반환 모양은 목업 시절과 같다.
- `src/components/TaskStream.vue` — 에이전트 진행 이벤트(TOKEN·TOOL_START/END·APPROVAL_REQUIRED·DONE·FAILED) 표시.
- `src/components/TaskApprovals.vue` — 변경 도구 앞에서 멈춘 작업 확인·거절 → 이어서 처리.
- 프록시: 개발은 `vite.config.js`, 운영은 `nginx.conf.template`. `/api/ai/*`는 백엔드 중계가 생기기 전까지만 에이전트로 간다.

## 배포 (compose)
```yaml
  frontend:
    build: ./apps/admin_web
    ports: ["80:80"]
    environment:
      BACKEND_UPSTREAM: http://backend:8000
      AGENT_UPSTREAM: http://agent:8002      # /ai/tasks 중계 전까지만
    depends_on: [backend]
```

## 백엔드에 요청한 것 (없어서 화면이 비거나 단순화된 곳)
- `GET /projects` — 프로젝트별 비용 표. 지금은 알림 상세에서 아는 프로젝트만 보인다.
- `GET/PATCH /departments` — 팀별 자동 발송 스위치·Slack 채널. 지금은 읽기 전용 목록.
- `GET /usage`의 월 단위 집계 — 홈의 월별 추이는 계약 사용량을 주 단위로 묶어 대신한다.
- 미지원 요청 응답에 부서 이름 — 지금은 부서 수만 있다.
- `POST /confirmations`의 `plan_id` 선택화 — 지금은 회수 요청을 먼저 만들어 붙인다.

색은 4개만 쓴다: `#111113` · `#f7f8f3` · `#dcef6d` · `#ffffff` (`src/styles.css`의 `:root`).
