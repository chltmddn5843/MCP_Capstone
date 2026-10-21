#!/usr/bin/env bash
# app 스키마를 지우고 다시 만든 뒤 시드를 넣는다. 사용: db/reset.sh
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d --wait postgres
psql() { docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -q -U "${POSTGRES_USER:-capstone}" -d "${POSTGRES_DB:-capstone}" "$@"; }
psql < db/schema.sql
uv run python db/seed/seed.py | psql
psql -c "SELECT relname AS table, n_live_tup AS rows FROM pg_stat_user_tables WHERE schemaname='app' ORDER BY relname;"
