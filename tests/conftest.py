"""테스트는 실제 PostgreSQL에 붙는다. 먼저 `docker compose up -d postgres`.

세션 시작과 테스트마다 app 스키마를 지우고 시드를 다시 넣어, 테스트끼리 데이터가 섞이지 않게 한다.
"""

import os
import subprocess
import sys

os.environ["AGENT_URL"] = ""  # 백엔드가 테스트 중 실제 에이전트를 부르지 않게 (.env보다 먼저 정해 둔다)
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from apps.backend import db

ROOT = Path(__file__).resolve().parents[1]


def reset_db() -> None:
    seed = subprocess.run([sys.executable, str(ROOT / "db/seed/seed.py")], capture_output=True, text=True, check=True).stdout
    with db.engine.begin() as c:
        raw = c.connection.driver_connection  # psycopg 직접: 파라미터 없이 여러 문장 실행 (% 해석 안 함)
        raw.execute((ROOT / "db/schema.sql").read_text(encoding="utf-8"))
        raw.execute(seed.replace("BEGIN;", "").replace("COMMIT;", ""))


try:
    reset_db()
except OperationalError as e:
    sys.exit(f"PostgreSQL에 연결할 수 없습니다 ({db.DATABASE_URL}). `docker compose up -d postgres` 후 다시 실행하세요.\n{e}")


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_db()
