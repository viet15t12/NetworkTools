from __future__ import annotations

import sqlite3
from typing import Any

from .common import (
    db_connection,
    log_db_error,
    normalize_host,
    option_action_cfg,
    option_presence_action_cfg,
    pool_identity_changed,
    soft_delete,
)
from .validation import pool_values


def _pool_payload(
    pool: str,
    network: str,
    subnetmask: str,
    default_router: str,
    dns: str,
    lease: str,
) -> dict[str, Any]:
    return pool_values(pool, network, subnetmask, default_router, dns, lease)


def _insert_pool(
    conn: sqlite3.Connection,
    host: str,
    data: dict[str, Any],
    action_cfg: str | None = None,
) -> None:
    selected_actions = action_cfg or option_presence_action_cfg(data)
    conn.execute(
        """
        INSERT INTO t03_dhcp_pool
            (host, pool, network, subnetmask, defaut, dns, lease, sync_status, action_Cfg)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_apply', ?);
        """,
        (
            host,
            data["pool"],
            data["network"],
            data["subnetmask"],
            data["defaut"],
            data["dns"],
            data["lease"],
            selected_actions,
        ),
    )


def get_dhcp_pools(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                """
                SELECT dhcp_id, host, pool, network, subnetmask, defaut, dns, lease, sync_status, action_Cfg
                FROM t03_dhcp_pool
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY dhcp_id ASC;
                """,
                (host,),
            ).fetchall()
        return db._dict_rows(rows)
    except sqlite3.Error as exc:
        log_db_error("getDhcpPools", exc)
        return []


def add_dhcp_pool(
    db: Any,
    host: str,
    pool: str,
    network: str,
    subnetmask: str,
    default_router: str,
    dns: str,
    lease: str,
) -> bool:
    host = normalize_host(host)
    try:
        data = _pool_payload(pool, network, subnetmask, default_router, dns, lease)
    except ValueError:
        return False
    if not host or not data["pool"] or not data["network"] or not data["subnetmask"]:
        return False
    try:
        with db_connection(db) as conn:
            _insert_pool(conn, host, data)
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addDhcpPool", exc)
        return False


def update_dhcp_pool(
    db: Any,
    dhcp_id: int,
    pool: str,
    network: str,
    subnetmask: str,
    default_router: str,
    dns: str,
    lease: str,
) -> bool:
    try:
        data = _pool_payload(pool, network, subnetmask, default_router, dns, lease)
    except ValueError:
        return False
    if dhcp_id < 0 or not data["pool"] or not data["network"] or not data["subnetmask"]:
        return False
    try:
        with db_connection(db) as conn:
            current_row = conn.execute(
                """
                SELECT dhcp_id, host, pool, network, subnetmask, defaut, dns, lease
                FROM t03_dhcp_pool
                WHERE dhcp_id = ? AND sync_status != 'pending_delete';
                """,
                (dhcp_id,),
            ).fetchone()
            if current_row is None:
                return False

            current = dict(current_row)
            if pool_identity_changed(current, data):
                if not soft_delete(conn, "t03_dhcp_pool", "dhcp_id", dhcp_id):
                    return False
                _insert_pool(conn, current["host"], data)
            else:
                action_cfg = option_action_cfg(current, data)
                if action_cfg == "000":
                    return True
                cursor = conn.execute(
                    """
                    UPDATE t03_dhcp_pool
                    SET defaut = ?, dns = ?, lease = ?, action_Cfg = ?, sync_status = 'pending_apply'
                    WHERE dhcp_id = ?;
                    """,
                    (data["defaut"], data["dns"], data["lease"], action_cfg, dhcp_id),
                )
                if cursor.rowcount <= 0:
                    return False
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("updateDhcpPool", exc)
        return False


def delete_dhcp_pool(db: Any, dhcp_id: int) -> bool:
    try:
        with db_connection(db) as conn:
            deleted = soft_delete(conn, "t03_dhcp_pool", "dhcp_id", dhcp_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteDhcpPool", exc)
        return False
