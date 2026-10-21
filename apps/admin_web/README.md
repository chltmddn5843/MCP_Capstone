# admin_web — 관리자 웹 (Vue 3 + Vite)

와이어프레임(https://claude.ai/artifact/6nPHyWDmv1SGHgmiQZ4EkW)을 옮긴 관리자 화면. 백엔드 REST API에 연결된다.

```bash
cd apps/admin_web
npm install
npm run dev        # http://localhost:5173
```

통합 실행은 저장소 루트에서 `scripts/run_all.sh`를 사용한다. 이 화면이 관리자 화면의 기본 실행 경로다.
스크립트는 `npm --prefix apps/admin_web run dev`로 Vite를 실행한다.

| 경로 | 화면 | 기능 |
| --- | --- | --- |
| `/` | 홈 · 지금 확인할 일 | 전체 |
| `/inbox` | 승인 대기 · AI 의견 | 처리 요청 |
| `/licenses` | 구독·이용권 | F4 |
| `/cost` | 비용·사용량 · 급증 알림 | F3 |
| `/suggestions` | 자동 제안 기록 | F1 |
| `/needs` | 미지원 요청 · 팀 활용 | F5 |

## 백엔드 연결
- 화면은 `src/api.js`를 통해 백엔드 REST API를 호출한다.
- `vite.config.js`가 `/api/*`를 `localhost:8000`으로 넘긴다. 토큰은 `POST /auth/dev-login`(`emp_asset_01`)으로 받는다.
- 응답 스키마(`packages/schemas`)와 화면 모양이 다르면 변환은 `api.js` 안에서 한다.
- 화면 용어는 `src/labels.js`를 사용한다.

## 인증과 제한
- 별도 로그인 페이지 없이 최초 접속 시 `emp_asset_01`로 개발용 자동 로그인한다.
- 토큰은 브라우저 `localStorage`에 저장한다.
- 팀별 자동 발송 토글은 백엔드 API가 추가되기 전까지 읽기 전용이다.

색은 4개만 쓴다: `#111113` · `#f7f8f3` · `#dcef6d` · `#ffffff` (`src/styles.css`의 `:root`).
