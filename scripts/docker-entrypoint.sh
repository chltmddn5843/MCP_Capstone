#!/usr/bin/env bash
set -euo pipefail

if [ "${SKIP_DB_INIT:-0}" != "1" ] && ! uv run python - <<'PY'
from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as connection:
    exists = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'app'")
    ).scalar()
raise SystemExit(0 if exists else 1)
PY
then
  echo "Initializing database schema and seed data..."
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/schema.sql
  uv run python db/seed/seed.py | psql "$DATABASE_URL" -v ON_ERROR_STOP=1
fi

exec "$@"
