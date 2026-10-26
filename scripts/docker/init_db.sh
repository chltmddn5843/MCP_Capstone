#!/usr/bin/env sh
# docker compose의 db_init 서비스: DB에 업무 스키마(app.employees)가 없을 때만 스키마와 시드를 넣는다. 있으면 아무것도 지우지 않는다.
# SEED_MODE=demo(기본) → db/seed/seed.py (가상 회사 한빛제조 59명)
# SEED_MODE=team       → scripts/seed_team.py (실제 Slack 6명 테스트 회사. TEAM_ADMIN_PASSWORD 없으면 새로 만들어 로그에 한 번 출력)
# 처음부터 다시 넣으려면: docker compose down -v (DB 볼륨 삭제) 후 docker compose up -d
set -e
PSQL_URL=$(printf '%s' "$DATABASE_URL" | sed 's/+psycopg//')
for i in $(seq 1 60); do pg_isready -d "$PSQL_URL" -q && break; sleep 1; done
if [ "$(psql "$PSQL_URL" -tAc "SELECT to_regclass('app.employees') IS NOT NULL")" = "t" ]; then
  echo "db_init: 스키마가 이미 있습니다. 기존 데이터를 그대로 씁니다."
  exit 0
fi
echo "db_init: 스키마가 없어 새로 만듭니다 (SEED_MODE=${SEED_MODE:-demo})."
psql "$PSQL_URL" -v ON_ERROR_STOP=1 -q -f db/schema.sql
if [ "${SEED_MODE:-demo}" = "team" ]; then
  python scripts/seed_team.py --yes
else
  python db/seed/seed.py | psql "$PSQL_URL" -v ON_ERROR_STOP=1 -q
fi
psql "$PSQL_URL" -tAc "SELECT 'db_init: 직원 ' || count(*) || '명' FROM app.employees"
