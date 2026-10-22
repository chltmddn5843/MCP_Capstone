#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

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

prompt_value() {
  local key="$1" label="$2" secret="${3:-0}" current value
  current=$(env_value "$key")
  if [ -n "$current" ]; then
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

echo "MCP Capstone 로컬 시연 설정"
echo "Slack 앱 토큰은 입력 중 화면에 표시되지 않습니다."
prompt_value SLACK_USER_ID "본인 Slack 사용자 ID (예: U012ABCDEF)"
prompt_value SLACK_EMPLOYEE_ID "연결할 시드 직원 ID (예: emp_mkt_01)"
prompt_value SLACK_BOT_TOKEN "Slack Bot Token (xoxb-...)" 1
prompt_value SLACK_APP_TOKEN "Slack App Token (xapp-...)" 1
# SLACK_USER_MAP이 비어 있으면 SLACK_USER_ID → SLACK_EMPLOYEE_ID 한 명으로 연결된다 (apps/slack_bot/identity.py). 이미 있는 매핑은 그대로 둔다

# 외부 공개(터널)는 운영 모드로만: dev면 누구나 dev-login으로 관리자 토큰을 받는다
[ "$(env_value APP_ENV)" = prod ] || set_env APP_ENV prod
[ -n "$(env_value JWT_SECRET)" ] || set_env JWT_SECRET "$(openssl rand -base64 48 | tr -d '\n/+=')"

case "$(env_value SLACK_BOT_TOKEN)" in xoxb-*) ;; *) echo "Bot Token은 xoxb-로 시작해야 합니다."; exit 1 ;; esac
case "$(env_value SLACK_APP_TOKEN)" in xapp-*) ;; *) echo "App Token은 xapp-로 시작해야 합니다."; exit 1 ;; esac

echo
echo ".env 저장 완료: Slack ID=$(
  env_value SLACK_USER_ID
), 직원=$(env_value SLACK_EMPLOYEE_ID)"
echo "다음 단계: PostgreSQL 확인 → 백엔드/에이전트/웹/Slack/Cloudflare 실행"
