from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.auth import create_initial_admin, hash_password
from app.db import SQLITE_DB_PATH, init_db, transaction


TABLES = [
    "exams",
    "questions",
    "options",
    "strategies",
    "strategy_question_links",
]


def sqlite_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def ensure_owner(pg_conn) -> int:
    username = os.getenv("IMPORT_OWNER_USERNAME") or os.getenv("FIRST_ADMIN_USERNAME") or "remy"
    display_name = os.getenv("IMPORT_OWNER_DISPLAY_NAME") or os.getenv("FIRST_ADMIN_DISPLAY_NAME") or username
    password = os.getenv("IMPORT_OWNER_PASSWORD") or os.getenv("FIRST_ADMIN_PASSWORD") or "change-me-now"
    row = pg_conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
    if row:
        return int(row["id"])
    created = pg_conn.execute(
        """
        INSERT INTO users (username, display_name, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'admin', 1)
        RETURNING id
        """,
        (username, display_name, hash_password(password)),
    ).fetchone()
    return int(created["id"])


def insert_rows(pg_conn, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(columns))
    quoted_columns = ", ".join(columns)
    conflict = "id"
    updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col != "id"])
    sql = f"""
        INSERT INTO {table} ({quoted_columns})
        VALUES ({placeholders})
        ON CONFLICT ({conflict}) DO UPDATE SET {updates}
    """
    for row in rows:
        pg_conn.execute(sql, tuple(row[col] for col in columns))


def insert_user_rows(pg_conn, table: str, rows: list[dict], owner_id: int) -> None:
    if not rows:
        return
    for row in rows:
        row = dict(row)
        row["user_id"] = owner_id
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        quoted_columns = ", ".join(columns)
        if table == "attempts":
            conflict_sql = "ON CONFLICT (id) DO NOTHING"
        else:
            conflict_sql = """
                ON CONFLICT (user_id, question_id) DO UPDATE SET
                    active = EXCLUDED.active,
                    source = EXCLUDED.source,
                    wrong_count_delta = EXCLUDED.wrong_count_delta,
                    attempt_count_delta = EXCLUDED.attempt_count_delta,
                    learned_at = EXCLUDED.learned_at,
                    updated_at = EXCLUDED.updated_at
            """
        pg_conn.execute(
            f"INSERT INTO {table} ({quoted_columns}) VALUES ({placeholders}) {conflict_sql}",
            tuple(row[col] for col in columns),
        )


def refresh_sequences(pg_conn) -> None:
    for table in [*TABLES, "attempts", "wrong_items"]:
        row = pg_conn.execute(f"SELECT COALESCE(MAX(id), 1) AS max_id FROM {table}").fetchone()
        pg_conn.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true)", (table, row["max_id"]))


def migrate(sqlite_path: Path = SQLITE_DB_PATH) -> dict:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")
    init_db()
    create_initial_admin()
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    summary: dict[str, int] = {}
    with transaction() as pg_conn:
        owner_id = ensure_owner(pg_conn)
        for table in TABLES:
            rows = sqlite_rows(sqlite_conn, table)
            insert_rows(pg_conn, table, rows)
            summary[table] = len(rows)
        for table in ("attempts", "wrong_items"):
            rows = sqlite_rows(sqlite_conn, table)
            insert_user_rows(pg_conn, table, rows, owner_id)
            summary[table] = len(rows)
        refresh_sequences(pg_conn)
        summary["owner_user_id"] = owner_id
    sqlite_conn.close()
    return summary


if __name__ == "__main__":
    print(migrate())
