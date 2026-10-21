# Slack 봇 (담당: Agent+프론트)

직원 접점. Bolt + Socket Mode라 공개 URL이 필요 없다. 설계는 `docs/설계문서.md` 4·9절, 배포는 `docs/아키텍처.md` 9절(`slack_bot` 서비스, profile `slack`).

| 파일 | 역할 |
| --- | --- |
| `app.py` | 수신: DM·멘션 → 에이전트 작업 → 한 메시지에 진행 상황 갱신 → 답변. 버튼 3종 처리. 승인 필요 시 관리자 DM |
| `send.py` | 메시지 형식 5종(제안·확인 요청·승인 요청·알림·답변)의 Block Kit 빌더와 발송 함수. **백엔드 워커(notify 큐)가 import해서 쓴다** |
| `client.py` | 백엔드·에이전트 HTTP, SSE 소비 |
| `identity.py` | Slack 사용자 → 직원 토큰. 백엔드 `POST /auth/slack-exchange`가 생기면 그걸 쓰고, 그 전엔 `SLACK_USER_MAP` + dev-login |

## 준비
`.env`
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_USER_MAP={"U0XXXX":"emp_mkt_01","U0YYYY":"emp_asset_01"}   # Slack 사용자 id → 직원 id (JWT 전환 전 임시)
SLACK_ADMIN_USER_IDS=U0YYYY                                        # 처리 확인 DM을 받을 관리자
```
Slack 앱 설정: Socket Mode, Bot scopes(chat:write, im:history, im:read, im:write, app_mentions:read, channels:read, channels:join, channels:history, users:read), Events(message.im, app_mention, message.channels), Interactivity On, App Home의 Messages Tab On.

## 실행
```bash
uv run python -m apps.slack_bot --check   # 토큰·채널·매핑 점검
uv run python -m apps.slack_bot           # 백엔드(8000)·에이전트(8002)가 떠 있어야 한다
```

## 백엔드에 요청한 것
- `POST /auth/slack-exchange {slack_user_id}` (시스템 토큰 전용) → 해당 직원의 토큰. JWT 전환과 함께.
- notify 워커에서 `apps.slack_bot.send.send_suggestion / send_confirmation / send_alert` 호출. `departments.slack_channel_id`, `employees.slack_user_id` 사용.
