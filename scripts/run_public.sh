#!/usr/bin/env bash
# 공개 시연: .env를 운영 모드로 맞추고(처음 한 번 Slack 값 입력) → DB 준비 → 서버·Slack 봇·외부 공개 터널을 한 번에 띄운다. Ctrl+C로 전부 종료.
# 사용: scripts/run_public.sh   (필요: Docker, uv, npm, cloudflared)
# 데이터는 이 PC의 로컬 DB다. 접속자는 모두 이 DB를 같이 보고, 다른 PC와는 동기화되지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v cloudflared >/dev/null || { echo "cloudflared가 필요합니다: brew install cloudflared"; exit 1; }

ENV_FILE=.env
[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

env_value() {  # 값만 (뒤의 '# 주석'·공백 제외)
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); sub(/[ \t]*#.*$/, ""); gsub(/^[ \t]+|[ \t]+$/, ""); print; exit}' "$ENV_FILE"
}

set_env() {
  local key="$1" value="$2" tmp
  tmp=$(mktemp)
  awk -F= -v key="$key" '$1 != key' "$ENV_FILE" >"$tmp"
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  mv "$tmp" "$ENV_FILE"
}

prompt_value() {  # 비어 있을 때만 묻는다
  local key="$1" label="$2" secret="${3:-0}" value
  if [ -n "$(env_value "$key")" ]; then
    printf '%s: 이미 설정됨\n' "$label"
    return
  fi
  if [ "$secret" = "1" ]; then
    read -r -s -p "$label: " value
    printf '\n'
  else
    read -r -p "$label: " value
  fi
  [ -n "$value" ] || { echo "$key 는 필수입니다."; exit 1; }
  set_env "$key" "$value"
}

# 1. .env (이미 있는 값은 다시 묻지 않는다)
echo "공개 시연 설정. Slack 토큰은 입력 중 화면에 표시되지 않습니다."
prompt_value SLACK_USER_ID "본인 Slack 사용자 ID (예: U012ABCDEF)"
prompt_value SLACK_EMPLOYEE_ID "연결할 시드 직원 ID (예: emp_mkt_01)"
prompt_value SLACK_BOT_TOKEN "Slack Bot Token (xoxb-...)" 1
prompt_value SLACK_APP_TOKEN "Slack App Token (xapp-...)" 1
# SLACK_USER_MAP이 비어 있으면 SLACK_USER_ID → SLACK_EMPLOYEE_ID 한 명으로 연결된다 (apps/slack_bot/identity.py). 이미 있는 매핑은 그대로 둔다
case "$(env_value SLACK_BOT_TOKEN)" in xoxb-*) ;; *) echo "Bot Token은 xoxb-로 시작해야 합니다."; exit 1 ;; esac
case "$(env_value SLACK_APP_TOKEN)" in xapp-*) ;; *) echo "App Token은 xapp-로 시작해야 합니다."; exit 1 ;; esac
# 외부 공개는 운영 모드로만: dev면 누구나 dev-login으로 관리자 토큰을 받는다
[ "$(env_value APP_ENV)" = prod ] || set_env APP_ENV prod
[ -n "$(env_value JWT_SECRET)" ] || set_env JWT_SECRET "$(openssl rand -base64 48 | tr -d '\n/+=')"

# 2. DB: 스키마가 없을 때만 시드를 넣는다 (기존 데이터는 지우지 않는다)
docker compose up -d --wait postgres
if ! docker compose exec -T postgres psql -U "${POSTGRES_USER:-capstone}" -d "${POSTGRES_DB:-capstone}" -tAc "SELECT to_regclass('app.employees')" | grep -q 'app.employees'; then
  echo "DB 스키마가 없어 초기화합니다."
  db/reset.sh
fi

# 3. 시스템 토큰: prod에서는 dev.sys가 막힌다. sys 계정 JWT(1년)를 .env의 JWT_SECRET으로 발급
case "$(env_value SYSTEM_TOKEN)" in eyJ*) ;; *) set_env SYSTEM_TOKEN "$(uv run python -m apps.backend.auth)" ;; esac

# 4. 서버 + Slack 봇 + 터널
SLACK=1 TUNNEL=1 exec scripts/run_all.sh
