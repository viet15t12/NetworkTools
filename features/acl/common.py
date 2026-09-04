"""Shared utilities for the ACL persistence.

Re-uses the same patterns as features/dhcp/common.py.
"""
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from typing import Any


@contextmanager
def db_connection(db: Any):
    conn = db._connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def normalize_host(value: Any) -> str:
    return text_or_default(value, "")


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def text_or_default(value: Any, default: str) -> str:
    text = text_or_none(value)
    return text if text is not None else default


def int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def int_or_default(value: Any, default: int) -> int:
    result = int_or_none(value)
    return result if result is not None else default


def log_db_error(operation: str, exc: sqlite3.Error) -> None:
    print(f"[db/acl] {operation} failed: {exc}", file=sys.stderr)


def soft_delete(conn: sqlite3.Connection, table: str, id_column: str, id_value: int) -> bool:
    row = conn.execute(
        f"SELECT sync_status FROM {table} WHERE {id_column} = ?;",
        (id_value,),
    ).fetchone()
    if row is None:
        return False
    if row[0] is None or row[0] == "pending_apply":
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE {id_column} = ?;", (id_value,)
        )
    else:
        cursor = conn.execute(
            f"UPDATE {table} SET sync_status = 'pending_delete' WHERE {id_column} = ?;",
            (id_value,),
        )
    return cursor.rowcount > 0
