# Slack 봇 (담당: Agent+프론트)

Slack Bolt, Socket Mode. 설계 문서 9절 메시지 5종.
직원 메시지 → `POST /agent/runs` (apps/agent_runtime) → SSE 이벤트를 받아 답장. 버튼 응답은 백엔드 REST(`/suggestions/{id}/feedback`, `/confirmations/{id}/answer`)로 직접.
만들 파일: `app.py`.
