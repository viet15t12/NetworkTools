from __future__ import annotations

import sqlite3
from typing import Any


def read_bindings(conn: sqlite3.Connection, acl_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT b.id, b.iface_id, b.direction, b.sync_status,
                  i.interface_name
           FROM t05_router_iface_acl AS b
           LEFT JOIN t02_interface_name AS i ON i.iface_id = b.iface_id
           WHERE b.acl_id = ? AND b.sync_status != 'pending_delete'""", (acl_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def replace_bindings(
    conn: sqlite3.Connection, acl_id: int, host: str, bindings: list[dict[str, Any]],
) -> None:
    conn.execute(
        "UPDATE t05_router_iface_acl SET sync_status = 'pending_delete' WHERE acl_id = ? AND sync_status != 'pending_delete'", (acl_id,),
    )
    seen: set[tuple[int, str]] = set()
    for binding in bindings:
        iface_id = int(binding.get("iface_id") or 0)
        direction = "out" if str(binding.get("direction") or "in").lower() == "out" else "in"
        key = (iface_id, direction)
        if iface_id <= 0 or key in seen:
            continue
        seen.add(key)
        exists = conn.execute(
            """SELECT 1 FROM t02_interface_name
               WHERE iface_id = ? AND host = ? AND COALESCE(sync_status, 'pending_apply') != 'pending_delete'""", (iface_id, host),
        ).fetchone()
        if exists is None:
            raise sqlite3.IntegrityError(f"Interface {iface_id} does not belong to ACL host {host}")
        conn.execute(
            """INSERT INTO t05_router_iface_acl (iface_id, acl_id, direction, sync_status)
               VALUES (?, ?, ?, 'pending_apply')
               ON CONFLICT(iface_id, direction)
               DO UPDATE SET acl_id = excluded.acl_id, sync_status = 'pending_apply'""", (iface_id, acl_id, direction),
        )


def mark_bindings_deleted(conn: sqlite3.Connection, acl_id: int) -> None:
    conn.execute(
        "UPDATE t05_router_iface_acl SET sync_status = 'pending_delete' WHERE acl_id = ? AND sync_status != 'pending_delete'", (acl_id,),
    )
