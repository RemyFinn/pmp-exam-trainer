from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SQLITE_DB_PATH = DATA_DIR / "pmp.sqlite"
SCHEMA_PATH = ROOT_DIR / "schema.sql"


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. Use PostgreSQL locally or in production.")
    return database_url


def get_connection() -> Connection:
    return Connection.connect(get_database_url(), row_factory=dict_row)


@contextmanager
def transaction() -> Iterator[Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with transaction() as conn:
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def row_to_dict(row: dict | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
