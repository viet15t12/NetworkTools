from __future__ import annotations

import sqlite3
from typing import Any

from .child_writers import insert_child_row, update_child_row
from .common import int_or_zero_value, normalize_process, text


CHILD_TABLE_FIELDS = {
    "t04_eigrp_networks": "networks",
    "t04_router_iface_eigrp": "interface_settings",
    "t04_eigrp_passive_interfaces": "passive_interfaces",
    "t04_eigrp_distribute_lists": "distribute_lists",
    "t04_eigrp_offset_lists": "offset_lists",
    "t04_eigrp_redistribute": "redistribute",
}

CHILD_TABLES = tuple(CHILD_TABLE_FIELDS)


def child_identity_key(table: str, row: dict[str, Any]) -> tuple[Any, ...]:
    if table == "t04_eigrp_networks":
        return (text(row.get("network")), text(row.get("wildcard")), text(row.get("interface_name")))
    if table == "t04_router_iface_eigrp":
        return (text(row.get("interface_name")),)
    if table == "t04_eigrp_passive_interfaces":
        return (text(row.get("interface_name")), text(row.get("mode")) or "passive")
    if table == "t04_eigrp_distribute_lists":
        return (text(row.get("list_name")), text(row.get("direction")) or "in", text(row.get("interface_name")))
    if table == "t04_eigrp_offset_lists":
        return (
            text(row.get("list_name")),
            text(row.get("direction")) or "in",
            int_or_zero_value(row.get("value")),
            text(row.get("interface_name")),
        )
    if table == "t04_eigrp_redistribute":
        return (text(row.get("protocol")), text(row.get("route_map")))
    raise ValueError(f"Unsupported table for key extraction: {table}")


def normalized_child_rows(db: Any, process: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return list(normalize_process(db, process).get(field, []))


def load_child_rows(conn: sqlite3.Connection, eigrp_id: int, table: str) -> list[dict[str, Any]]:
    if table == "t04_eigrp_networks":
        rows = conn.execute(
            "SELECT id, network, wildcard, interface_name FROM t04_eigrp_networks WHERE eigrp_id = ? AND sync_status != 'pending_delete' ORDER BY id ASC;",
            (eigrp_id,),
        ).fetchall()
    elif table == "t04_router_iface_eigrp":
        rows = conn.execute(
            """
            SELECT r.id, i.interface_name, r.bandwidth, r.delay,
                   r.hello_interval, r.hold_time, r.auth_key_chain,
                   r.summary_ip, r.summary_mask, r.split_horizon,
                   r.bandwidth_percent, r.next_hop_self, r.bfd,
                   r.bfd_tx, r.bfd_rx, r.bfd_multiplier
            FROM t04_router_iface_eigrp AS r
            JOIN t02_interface_name AS i ON i.iface_id = r.iface_id
            WHERE r.eigrp_id = ? AND r.sync_status != 'pending_delete'
            ORDER BY r.id ASC;
            """,
            (eigrp_id,),
        ).fetchall()
    elif table == "t04_eigrp_passive_interfaces":
        rows = conn.execute(
            "SELECT id, interface_name, mode FROM t04_eigrp_passive_interfaces WHERE eigrp_id = ? AND sync_status != 'pending_delete' ORDER BY id ASC;",
            (eigrp_id,),
        ).fetchall()
    elif table == "t04_eigrp_distribute_lists":
        rows = conn.execute(
            "SELECT id, list_name, direction, interface_name FROM t04_eigrp_distribute_lists WHERE eigrp_id = ? AND sync_status != 'pending_delete' ORDER BY id ASC;",
            (eigrp_id,),
        ).fetchall()
    elif table == "t04_eigrp_offset_lists":
        rows = conn.execute(
            "SELECT id, list_name, direction, value, interface_name FROM t04_eigrp_offset_lists WHERE eigrp_id = ? AND sync_status != 'pending_delete' ORDER BY id ASC;",
            (eigrp_id,),
        ).fetchall()
    elif table == "t04_eigrp_redistribute":
        rows = conn.execute(
            """
            SELECT id, protocol, route_map, metric_bw, metric_delay,
                   metric_reliability, metric_load, metric_mtu
            FROM t04_eigrp_redistribute
            WHERE eigrp_id = ? AND sync_status != 'pending_delete'
            ORDER BY id ASC;
            """,
            (eigrp_id,),
        ).fetchall()
    else:
        raise ValueError(f"Unsupported child table: {table}")
    return [dict(row) for row in rows]


def sync_eigrp_child_table(
    conn: sqlite3.Connection,
    db: Any,
    eigrp_id: int,
    process: dict[str, Any],
    table: str,
    *,
    replace_all: bool,
) -> None:
    field = CHILD_TABLE_FIELDS[table]
    submitted_rows = normalized_child_rows(db, process, field)

    if replace_all:
        conn.execute(f"UPDATE {table} SET sync_status = 'pending_delete' WHERE eigrp_id = ?;", (eigrp_id,))

    existing_rows = load_child_rows(conn, eigrp_id, table) if not replace_all else []
    existing_by_key = {child_identity_key(table, row): row for row in existing_rows}
    submitted_by_key = {child_identity_key(table, row): row for row in submitted_rows}

    for key, existing in existing_by_key.items():
        if key not in submitted_by_key:
            conn.execute(f"UPDATE {table} SET sync_status = 'pending_delete' WHERE id = ?;", (existing["id"],))

    for key, submitted in submitted_by_key.items():
        existing = existing_by_key.get(key)
        if existing is None:
            insert_child_row(conn, db, eigrp_id, table, submitted)
            continue
        current = dict(existing)
        current.pop("id", None)
        if current != submitted:
            update_child_row(conn, db, existing["id"], table, submitted)
        else:
            conn.execute(f"UPDATE {table} SET sync_status = 'pending_apply' WHERE id = ?;", (existing["id"],))
