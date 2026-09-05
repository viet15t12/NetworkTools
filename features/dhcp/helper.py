from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from typing import Any

from .common import db_connection, log_db_error, normalize_host, soft_delete
from .validation import ipv4


def get_dhcp_helper_addresses(db: Any, host: str) -> list[dict[str, Any]]:
    host = normalize_host(host)
    if not host:
        return []
    try:
        with db_connection(db) as conn:
            rows = conn.execute(
                """
                SELECT h.id, h.iface_id, i.interface_name, h.helper_ip, h.sync_status
                FROM t03_router_iface_helper AS h
                JOIN t02_interface_name AS i ON i.iface_id = h.iface_id
                WHERE i.host = ? AND h.sync_status != 'pending_delete' AND i.sync_status != 'pending_delete'
                ORDER BY i.interface_name COLLATE NOCASE, h.id ASC;
                """,
                (host,),
            ).fetchall()
        return db._dict_rows(rows)
    except sqlite3.Error as exc:
        log_db_error("getDhcpHelperAddresses", exc)
        return []


def add_dhcp_helper_address(db: Any, iface_id: int, helper_ip: str) -> bool:
    try:
        helper = ipv4(helper_ip, "helper address")
    except ValueError:
        return False
    if iface_id < 0:
        return False
    try:
        with db_connection(db) as conn:
            conn.execute(
                """
                INSERT INTO t03_router_iface_helper (iface_id, helper_ip, sync_status)
                VALUES (?, ?, 'pending_apply')
                ON CONFLICT(iface_id, helper_ip)
                DO UPDATE SET sync_status = 'pending_apply';
                """,
                (iface_id, helper),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        log_db_error("addDhcpHelperAddress", exc)
        return False


def delete_dhcp_helper_address(db: Any, helper_id: int) -> bool:
    try:
        with db_connection(db) as conn:
            deleted = soft_delete(conn, "t03_router_iface_helper", "id", helper_id)
            conn.commit()
        return deleted
    except sqlite3.Error as exc:
        log_db_error("deleteDhcpHelperAddress", exc)
        return False
