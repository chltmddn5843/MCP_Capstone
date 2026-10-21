# admin_web — 관리자 웹 (Vue 3 + Vite)

와이어프레임(https://claude.ai/artifact/6nPHyWDmv1SGHgmiQZ4EkW)을 옮긴 관리자 화면. 지금은 목업 데이터로 동작한다.

```bash
cd apps/admin_web
npm install
npm run dev        # http://localhost:5173
node check.mjs     # api.js 상태 전이 확인
```

| 경로 | 화면 | 기능 |
| --- | --- | --- |
| `/` | 홈 · 지금 확인할 일 | 전체 |
| `/inbox` | 승인 대기 · AI 의견 | 처리 요청 |
| `/licenses` | 구독·이용권 | F4 |
| `/cost` | 비용·사용량 · 급증 알림 | F3 |
| `/suggestions` | 자동 제안 기록 | F1 |
| `/needs` | 미지원 요청 · 팀 활용 | F5 |

## 백엔드 연결
- 화면은 `src/api.js`만 부른다. 함수마다 대응 REST 경로가 주석으로 있다. 본문을 `request('/경로')`로 바꾸고 `src/mock.js`를 지운다.
- `vite.config.js`가 `/api/*`를 `localhost:8000`으로 넘긴다. 토큰은 `POST /auth/dev-login`(`emp_asset_01`)으로 받는다.
- 응답 스키마(`packages/schemas`)와 화면 모양이 다르면 변환은 `api.js` 안에서 한다.
- 화면 용어는 `src/labels.js` (= `apps/admin_ui/labels.py`).

색은 4개만 쓴다: `#111113` · `#f7f8f3` · `#dcef6d` · `#ffffff` (`src/styles.css`의 `:root`).
