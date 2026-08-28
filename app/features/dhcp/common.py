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


def option_action_cfg(current: dict[str, Any], submitted: dict[str, Any]) -> str:
    fields = ("defaut", "dns", "lease")
    bits = ["1" if str(current.get(field) or "") != str(submitted.get(field) or "") else "0" for field in fields]
    return "".join(bits)


def option_presence_action_cfg(data: dict[str, Any]) -> str:
    """Select only optional commands that have values on a newly created pool."""
    lease = str(data.get("lease") or "1").strip().lower()
    return "".join(
        (
            "1" if str(data.get("defaut") or "").strip() else "0",
            "1" if str(data.get("dns") or "").strip() else "0",
            "1" if lease not in {"", "1"} else "0",
        )
    )


def pool_identity_changed(current: dict[str, Any], submitted: dict[str, Any]) -> bool:
    return any(
        str(current.get(field) or "") != str(submitted.get(field) or "")
        for field in ("pool", "network", "subnetmask")
    )


def log_db_error(operation: str, exc: sqlite3.Error) -> None:
    print(f"[db] {operation} failed: {exc}", file=sys.stderr)


def soft_delete(conn: sqlite3.Connection, table: str, id_column: str, id_value: int) -> bool:
    row = conn.execute(
        f"SELECT sync_status FROM {table} WHERE {id_column} = ?;",
        (id_value,),
    ).fetchone()
    if row is None:
        return False
    # A local draft has never existed on the device.  Removing it must cancel
    # the pending apply instead of queuing a phantom device-side delete.
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
