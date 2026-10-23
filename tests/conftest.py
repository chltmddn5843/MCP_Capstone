"""테스트는 실제 PostgreSQL에 붙는다. 먼저 `docker compose up -d postgres`.

개발 DB(capstone)와 따로 테스트 DB(capstone_test)를 쓴다. 없으면 만든다. 떠 있는 서버·Slack 봇의 데이터는 건드리지 않는다.
세션 시작과 테스트마다 app 스키마를 지우고 시드를 다시 넣어, 테스트끼리 데이터가 섞이지 않게 한다.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

import psycopg  # noqa: E402

# 앱 모듈을 import하기 전에 정한다 (load_dotenv는 이미 있는 값을 안 바꾼다)
os.environ["APP_ENV"] = "dev"  # 테스트는 dev.<id> 토큰을 쓴다. .env가 prod여도
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://capstone:capstone@localhost:5432/capstone_test")
os.environ["F3_DEMO_HEAVY"] = "emp_md_01,emp_cs_01"  # 시드 기준. 로컬 .env(6명 테스트 회사 등)의 값이 테스트에 섞이지 않게


def ensure_test_db(url: str) -> None:
    server, name = url.replace("+psycopg", "", 1).rsplit("/", 1)
    with psycopg.connect(f"{server}/postgres", autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')


from apps.backend import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def reset_db() -> None:
    seed = subprocess.run([sys.executable, str(ROOT / "db/seed/seed.py")], capture_output=True, text=True, check=True).stdout
    with db.engine.begin() as c:
        raw = c.connection.driver_connection  # psycopg 직접: 파라미터 없이 여러 문장 실행 (% 해석 안 함)
        raw.execute((ROOT / "db/schema.sql").read_text(encoding="utf-8"))
        raw.execute(seed.replace("BEGIN;", "").replace("COMMIT;", ""))


try:
    ensure_test_db(os.environ["DATABASE_URL"])
    reset_db()
    with db.engine.begin() as c:  # 에이전트 작업 이력·checkpoint(agent 스키마)는 세션 시작 때 한 번 비운다. 에이전트 앱이 다시 만든다
        c.exec_driver_sql("DROP SCHEMA IF EXISTS agent CASCADE")
except (OperationalError, psycopg.OperationalError) as e:
    sys.exit(f"PostgreSQL에 연결할 수 없습니다 ({db.DATABASE_URL}). `docker compose up -d postgres` 후 다시 실행하세요.\n{e}")


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_db()
