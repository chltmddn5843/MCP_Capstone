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
| `/login` | 로그인 (사번·이메일 + 비밀번호, 개발 서버에선 시연 계정 버튼) | 인증 |
| `/signup` | 첫 관리자 가입 (회사가 없을 때만, 로그인 화면에 링크) | 초기 설정 |
| `/setup` | 초기 설정 마법사 겸 회사 설정: 부서·직원 → **좌석 구조**(층·부서 구역·책상 만들기·없애기, `POST/DELETE /desks`) → 구독 제품 → AI 모델·API 프로젝트 → 연간 예산 → 확인. 설정을 마치기 전에는 다른 화면이 이리로 온다 | 초기 설정 |
| `/cost/vendors` | 비용·사용량 › 벤더별: 공급사별 이번 달 비용(좌석 정액 + API 사용량), 모델별 비용·예산 도넛, 프로젝트별 API 비용·예산 초과 | F3 |
| `/cost/teams` | 비용·사용량 › 팀별: **팀별 실시간 사용량**(확인이 필요한 팀이 맨 위, 배지 = 2배 이상 N석 › API 예산 초과 › 빠름 › 이용권 확인, 이름 칩을 누르면 그 자리로) + 층별 **좌석 배치도** (책상은 DB `desks`): 층 탭·좌석 구조 편집·신입 등록 툴바, 구역 배지, 자리마다 도구·이용권 상태·최근 30일 사용일, 오늘 토큰 소비 속도 색·호버 (30초 갱신). 팀·자리를 고르면 오른쪽에 **왜 확인이 필요한가 → 이렇게 해 보세요**(`insight.js` 규칙) → **AI로 현재 작업 분석**(analyze_seat_usage, 패널 안에서 실행·세션 캐시). 패널 순서는 ① 왜 확인이 필요한가 → ② AI 분석 → ③ 해결책 선택지(토큰 경보는 분석 뒤에 열림, 이용권 확인은 바로). 선택지의 사용 의사 확인 요청·회수 요청·예산 검토 요청은 실행 버튼, 보낸 확인 요청은 상태(보냄·답함·기한 지남)로, 본인 Slack 안내는 상태만. 자리 앉히기·옮기기·비우기 (신입 등록은 회사 설정 › 부서·직원, 층·구역·책상 만들기는 회사 설정 › 좌석 구조). 옛 `/seats`는 여기로 redirect | F3·F4 |
| `/needs` | **미도입 제품 신청** (PRD S9): 직원이 사내 등록 제품에 없는 제품을 신청해 '사내 미도입'으로 반려된 이력(purchase_review)을 제품 이름으로 묶어 본다. 같은 제품 3건·2개 부서 이상이면 검토 기준 충족, [구매 검토 요청]으로 책임자 결정(승인 대기)에 올린다 | F3 |
| `/` | 홈 · 지금 확인할 일 | 전체 |
| `/inbox` | 승인 대기 · AI 의견 · **AI 비서 처리 확인** | 처리 요청 |
| `/licenses` | 구독·이용권 | F4 |
| `/suggestions` | 자동 제안 기록 · 새 모델 카드 뉴스 미리보기 · **[출시 시뮬레이션]** (감지 → AI 카드 작성 진행 표시 → 발송 배치) · 카드 미리보기(전 직무) — Slack에는 받는 사람 직무 줄만 나간다 | F1 |
| `/assistant` | **AI 비서에게 묻기** (진행 스트림, 내 요청) | 전체 |
| `/key/:id` | 직원용 API 키 확인 (Slack 일회용 링크, 사이드바 없음, [키 보기]를 눌러야 한 번만 열림) | F4 |

## 구조
- `src/request.js` — fetch 공통(`/api/*`), 토큰(`POST /auth/login` JWT를 `localStorage.token`에, 없거나 401이면 `/login`), `login`·`devLogin`(개발 서버 전용)·`logout`, SSE 스트리밍(`streamTask`), 에이전트 작업 API.
- `src/api.js` — 화면별 데이터 함수. 함수 이름·반환 모양은 목업 시절과 같다.
- `src/components/TaskStream.vue` — 에이전트 진행 이벤트(TOKEN·TOOL_START/END·APPROVAL_REQUIRED·DONE·FAILED) 표시.
- `src/components/TaskApprovals.vue` — 변경 도구 앞에서 멈춘 작업 확인·거절 → 이어서 처리.
- 프록시: 개발은 `vite.config.js`, 운영은 `nginx.conf.template`. `/api/*` 전부 백엔드로 간다(AI 비서는 백엔드가 에이전트로 중계).

## 배포 (compose)
```yaml
  frontend:
    build: ./apps/admin_web
    ports: ["80:80"]
    environment:
      BACKEND_UPSTREAM: http://backend:8000
    depends_on: [backend]
```

## 백엔드에 요청한 것 (없어서 화면이 비거나 단순화된 곳)
- `GET /projects` — 프로젝트별 비용 표. 지금은 알림 상세에서 아는 프로젝트만 보인다.
- `GET/PATCH /departments` — 팀별 자동 발송 스위치·Slack 채널. 지금은 읽기 전용 목록.
- `GET /usage`의 월 단위 집계 — 홈의 월별 추이는 계약 사용량을 주 단위로 묶어 대신한다.
- `POST /confirmations`의 `plan_id` 선택화 — 지금은 회수 요청을 먼저 만들어 붙인다.

색은 4개만 쓴다: `#111113` · `#f7f8f3` · `#dcef6d` · `#ffffff` (`src/styles.css`의 `:root`).
