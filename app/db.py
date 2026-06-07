from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "pmp.sqlite"
SCHEMA_PATH = ROOT_DIR / "schema.sql"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
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
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        if "elapsed_seconds" not in columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN elapsed_seconds INTEGER")
        wrong_columns = {row["name"] for row in conn.execute("PRAGMA table_info(wrong_items)").fetchall()}
        if "wrong_count_delta" not in wrong_columns:
            conn.execute("ALTER TABLE wrong_items ADD COLUMN wrong_count_delta INTEGER NOT NULL DEFAULT 0")
        if "attempt_count_delta" not in wrong_columns:
            conn.execute("ALTER TABLE wrong_items ADD COLUMN attempt_count_delta INTEGER NOT NULL DEFAULT 0")


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
