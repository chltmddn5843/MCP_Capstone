"""PostgreSQL 연결. 쿼리는 SQL 그대로 쓰고(text), 결과는 dict 목록으로 돌려준다.

스키마는 db/schema.sql(app 스키마). 로컬은 `db/reset.sh`로 띄우고 시드를 넣는다.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://capstone:capstone@localhost:5432/capstone")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"options": "-csearch_path=app"})


def rows(sql: str, conn=None, **params) -> list[dict]:
    if conn is not None:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text(sql), params).mappings()]


def one(sql: str, conn=None, **params) -> dict | None:
    r = rows(sql, conn, **params)
    return r[0] if r else None


@contextmanager
def tx():
    """한 트랜잭션. 블록을 정상 종료하면 commit, 예외면 rollback."""
    with engine.begin() as c:
        yield c


def js(v) -> str:
    """jsonb 파라미터용. SQL 쪽에서 CAST(:x AS jsonb)로 받는다."""
    return json.dumps(v, ensure_ascii=False, default=str)
