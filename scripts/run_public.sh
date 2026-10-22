#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v cloudflared >/dev/null || { echo "cloudflared가 필요합니다: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"; exit 1; }
scripts/setup_local.sh
docker compose up -d --wait postgres
if ! docker compose exec -T postgres psql -U "${POSTGRES_USER:-capstone}" -d "${POSTGRES_DB:-capstone}" -tAc "SELECT to_regclass('app.employees')" | grep -q 'app.employees'; then
  echo "DB 스키마가 없어 초기화합니다."
  db/reset.sh
fi
if ! grep -qE '^SYSTEM_TOKEN=eyJ' .env; then  # prod에서는 dev.sys가 막힌다. sys 계정 JWT(1년)를 .env의 JWT_SECRET으로 발급
  tok=$(uv run python -m apps.backend.auth)
  { grep -v '^SYSTEM_TOKEN=' .env; echo "SYSTEM_TOKEN=$tok"; } >.env.tmp && mv .env.tmp .env
fi
SLACK=1 TUNNEL=1 exec scripts/run_all.sh
