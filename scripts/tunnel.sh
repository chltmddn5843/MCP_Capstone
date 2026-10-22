#!/usr/bin/env bash
# 외부 공개: 로컬 화면(:5173)을 Cloudflare Quick Tunnel로 연다. Ctrl+C로 종료.
# 터널 주소(https://xxxx.trycloudflare.com)는 켤 때마다 바뀐다. 이 PC가 Cloudflare 계정에 wrangler login 돼 있으면
# 주소를 KV에 적어 고정 주소(https://nodi-admin.chltmddn5843.workers.dev)의 /api 도 이 터널로 보낸다. 아니면 그 단계만 건너뛴다.
# Quick Tunnel은 Cloudflare 쪽에서 사라질 수 있다("Tunnel not found"). 15초마다 보고, 끊기면 새로 연다.
# 사용: scripts/run_all.sh 를 띄운 뒤 다른 터미널에서 scripts/tunnel.sh  (또는 TUNNEL=1 scripts/run_all.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
app_env="${APP_ENV:-$(awk -F= '$1=="APP_ENV"{sub(/[ \t]*#.*$/, "", $2); gsub(/[ \t]/, "", $2); print $2}' .env 2>/dev/null)}"
[ "$app_env" = prod ] || { echo "외부 공개는 APP_ENV=prod에서만 연다 (dev면 누구나 dev-login으로 관리자 토큰을 받는다). scripts/run_public.sh 를 쓰세요."; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared가 필요합니다: brew install cloudflared"; exit 1; }
mkdir -p logs
log=logs/cloudflare.log
pid=""
trap '[ -n "$pid" ] && kill "$pid" 2>/dev/null' EXIT
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
  echo "$(date '+%H:%M:%S') 터널 $url"
  if (cd apps/admin_web && npx --no-install wrangler kv key put origin "$url" --binding TUNNEL --remote >/dev/null 2>&1); then
    echo "  고정 주소 https://nodi-admin.chltmddn5843.workers.dev 의 /api 도 1분 안에 이 터널로 바뀝니다."
  else
    echo "  (고정 주소는 갱신하지 않음: 이 PC가 Cloudflare 계정에 wrangler login 돼 있지 않다. 위 터널 주소로 접속)"
  fi
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
