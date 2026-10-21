# 관리자 콘솔 (Vue 3)

Vite + Vue 3 + Vue Router + Pinia + Element Plus. 브라우저는 `/api/*`만 부르고, nginx(운영)·Vite(개발)가 백엔드로 넘긴다. 에이전트는 공개하지 않는다.

| 화면 | 경로 | 역할 |
| --- | --- | --- |
| 이용권 · 비용 급증 알림 · 승인 대기 · 미지원 요청 · 활용 현황·자동 제안 | `/licenses` `/alerts` `/approvals` `/unmet` `/adoption` | 관리자 |
| AI 비서 · 내 요청 | `/assistant` `/history` | 전원 |
| 내 업무와 이용권 | `/mine` | 직원 (Slack 대신 쓰는 시연용) |

## 개발
```bash
cd frontend && npm install
npm run dev            # http://localhost:5173  (백엔드 8000, 에이전트 8002가 떠 있어야 함)
npm run build          # dist/
```
개발 프록시: `/api/ai/*` → 에이전트, `/api/*` → 백엔드 (`vite.config.js`). 백엔드가 `/ai/tasks` 중계를 제공하면 `/api/ai` 항목을 지운다.

## 배포 (compose)
```yaml
  frontend:
    build: ./frontend
    ports: ["80:80"]
    environment:
      BACKEND_UPSTREAM: http://backend:8000
      AGENT_UPSTREAM: http://agent:8002      # 중계 전까지만
    depends_on: [backend]
```
`nginx.conf.template`의 `${BACKEND_UPSTREAM}`·`${AGENT_UPSTREAM}`은 컨테이너 시작 시 치환된다. SSE를 위해 `proxy_buffering off`.

## 용어
`src/labels.js`는 `apps/admin_ui/labels.py`와 같은 값을 유지한다 (docs/설계문서.md 0절).
