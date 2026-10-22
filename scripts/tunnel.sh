#!/usr/bin/env bash
# 로컬 화면(:5173)을 Cloudflare Quick Tunnel로 열고, 새 터널 주소를 KV에 적는다.
# 그러면 고정 주소(Workers, apps/admin_web/wrangler.jsonc)의 /api/* 가 이 터널로 간다. Ctrl+C로 종료.
# Quick Tunnel은 Cloudflare 쪽에서 사라질 수 있다("Tunnel not found"). 15초마다 보고, 끊기면 새로 열어 KV를 다시 적는다.
# 사용: scripts/run_all.sh 를 띄운 뒤 다른 터미널에서 scripts/tunnel.sh
set -euo pipefail
cd "$(dirname "$0")/.."
log=$(mktemp)
pid=""
trap '[ -n "$pid" ] && kill "$pid" 2>/dev/null; rm -f "$log"' EXIT
trap 'exit 0' INT TERM

start() {
  : >"$log"
  cloudflared tunnel --url http://localhost:5173 >"$log" 2>&1 &
  pid=$!
  local url=""
  for _ in $(seq 1 60); do
    url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$log" | head -1 || true)
    [ -n "$url" ] && break
    sleep 1
  done
  [ -n "$url" ] || { cat "$log"; echo "터널 주소를 받지 못했습니다."; return 1; }
  (cd apps/admin_web && npx wrangler kv key put origin "$url" --binding TUNNEL --remote)
  echo "$(date '+%H:%M:%S') 터널 $url — 고정 주소의 /api 가 1분 안에 이 터널로 바뀝니다."
}

start
while sleep 15; do
  if ! kill -0 "$pid" 2>/dev/null || grep -q 'Tunnel not found' "$log"; then
    echo "$(date '+%H:%M:%S') 터널이 끊겨 새로 엽니다."
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    start || sleep 30
  fi
done
