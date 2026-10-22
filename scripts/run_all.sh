#!/usr/bin/env bash
# 개발·시연용: 백엔드, 업무 MCP, 문서 MCP, 에이전트, Vue 관리자 화면을 한 번에 띄운다. Ctrl+C로 전부 종료.
# 사용: scripts/run_all.sh            (MCP 모드: 에이전트가 MCP 서버를 거쳐 도구 호출)
#       MCP=0 scripts/run_all.sh      (로컬 모드: 에이전트가 백엔드 REST 직접 호출, MCP 서버 안 띄움)
#       SLACK=1 TUNNEL=1 …            (Slack 봇·외부 공개 터널까지. 보통은 scripts/run_public.sh 로 부른다)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { cp .env.example .env; echo ".env 생성됨. OPENAI_API_KEY 등을 채우세요 (키 없으면 LLM_MODEL=fake)."; }
mkdir -p db logs
MCP="${MCP:-1}"
SLACK="${SLACK:-0}"
TUNNEL="${TUNNEL:-0}"
app_env="${APP_ENV:-$(awk -F= '$1=="APP_ENV"{sub(/[ \t]*#.*$/, "", $2); gsub(/[ \t]/, "", $2); print $2}' .env)}"
if [ "$TUNNEL" = "1" ] && [ "$app_env" != "prod" ]; then
  echo "TUNNEL=1(외부 공개)은 APP_ENV=prod에서만 켭니다. dev면 누구나 dev-login으로 관리자 토큰을 받습니다."
  echo "scripts/run_public.sh 로 실행하면 .env를 운영 모드(APP_ENV·JWT_SECRET·SYSTEM_TOKEN)로 맞춰 준다."
  exit 1
fi
ports=(8000 8002 5173); [ "$MCP" = "1" ] && ports+=(8010 8011)
for port in "${ports[@]}"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "포트 $port 를 이미 다른 프로세스가 쓰고 있습니다. 이전 실행이 남아 있으면 종료하세요:"
    echo "  pkill -f 'uvicorn apps\.|apps.mcp_|vite'"
    exit 1
  fi
done
wait_port() { for i in $(seq 1 60); do lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 && return 0; sleep 0.5; done; echo "경고: 포트 $1 이(가) 30초 안에 열리지 않았습니다. logs/ 를 확인하세요."; return 1; }
pids=()
PATTERN='uvicorn apps\.|apps\.mcp_|vite'
shutdown() {
  echo; echo "종료 중…"
  kill "${pids[@]}" 2>/dev/null
  pkill -TERM -f "$PATTERN" 2>/dev/null
  for i in 1 2 3 4 5 6; do pgrep -f "$PATTERN" >/dev/null 2>&1 || break; sleep 0.5; done
  if pgrep -f "$PATTERN" >/dev/null 2>&1; then echo "응답 없는 프로세스를 강제 종료합니다."; pkill -KILL -f "$PATTERN" 2>/dev/null; fi
  echo "종료됨"; exit 0
}
trap shutdown INT TERM

uv run uvicorn apps.backend.main:app --port 8000 --timeout-graceful-shutdown 3 >logs/backend.log 2>&1 & pids+=($!)
if [ "$MCP" = "1" ]; then
  uv run python -m apps.mcp_work.server >logs/mcp_work.log 2>&1 & pids+=($!)
  uv run python -m apps.mcp_docs.server >logs/mcp_docs.log 2>&1 & pids+=($!)
  export MCP_WORK_URL="${MCP_WORK_URL:-http://localhost:8010/mcp}" MCP_DOCS_URL="${MCP_DOCS_URL:-http://localhost:8011/mcp}"
else
  export MCP_WORK_URL="" MCP_DOCS_URL=""
fi
wait_port 8000
if [ "$MCP" = "1" ]; then wait_port 8010; wait_port 8011; fi   # 에이전트는 MCP가 뜬 뒤에 띄운다
uv run uvicorn apps.agent_runtime.main:app --port 8002 --timeout-graceful-shutdown 3 >logs/agent.log 2>&1 & pids+=($!)
wait_port 8002

echo "backend  http://localhost:8000/docs"
[ "$MCP" = "1" ] && echo "mcp_work http://localhost:8010/mcp   mcp_docs http://localhost:8011/mcp"
echo "agent    http://localhost:8002/docs   (LLM_MODEL=${LLM_MODEL:-$(grep -E '^LLM_MODEL=' .env | cut -d= -f2-)}, MCP=$MCP)"
echo "admin_web http://localhost:5173       로그는 logs/*.log"
if [ ! -d apps/admin_web/node_modules ]; then npm --prefix apps/admin_web install; fi
npm --prefix apps/admin_web run dev -- --host 0.0.0.0 >logs/admin_web.log 2>&1 & pids+=($!)
wait_port 5173
if [ "$SLACK" = "1" ]; then
  uv run python -m apps.slack_bot >logs/slack_bot.log 2>&1 & pids+=($!)
  echo "slack_bot  실행 중 (logs/slack_bot.log)"
fi
if [ "$TUNNEL" = "1" ]; then
  scripts/tunnel.sh & pids+=($!)   # 주소는 이 터미널에 찍힌다. 끊기면 tunnel.sh가 다시 연다
fi
wait
