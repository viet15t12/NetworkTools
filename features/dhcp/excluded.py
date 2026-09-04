from __future__ import annotations

import sqlite3
from typing import Any

from .common import db_connection, log_db_error, normalize_host, soft_delete
from .validation import excluded_range


def get_excluded_addresses(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                """
                SELECT ex_id, host, start_ip, end_ip, sync_status
                FROM t03_excluded_address
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY ex_id ASC;
                """,
                (host,),
            ).fetchall()
        return db._dict_rows(rows)
    except sqlite3.Error as exc:
        log_db_error("getExcludedAddresses", exc)
        return []


def add_excluded_address(db: Any, host: str, start_ip: str, end_ip: str) -> bool:
    host = normalize_host(host)
    try:
        start, end = excluded_range(start_ip, end_ip)
    except ValueError:
        return False
    if not host:
        return False
    try:
        with db_connection(db) as conn:
            conn.execute(
                """
                INSERT INTO t03_excluded_address (host, start_ip, end_ip, sync_status)
                VALUES (?, ?, ?, 'pending_apply');
                """,
                (host, start, end),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addExcludedAddress", exc)
        return False


def delete_excluded_address(db: Any, ex_id: int) -> bool:
    try:
        with db_connection(db) as conn:
            deleted = soft_delete(conn, "t03_excluded_address", "ex_id", ex_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteExcludedAddress", exc)
        return False
