from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from typing import Any


def insert_child_row(conn: sqlite3.Connection, db: Any, eigrp_id: int, table: str, row: dict[str, Any]) -> None:
    if table == "t04_eigrp_networks":
        conn.execute(
            """
            INSERT INTO t04_eigrp_networks (eigrp_id, network, wildcard, interface_name, sync_status)
            VALUES (?, ?, ?, ?, 'pending_apply');
            """,
            (
                eigrp_id,
                db._str_or_none(row.get("network")),
                db._str_or_none(row.get("wildcard")),
                db._str_or_none(row.get("interface_name")),
            ),
        )
        return

    if table == "t04_router_iface_eigrp":
        interface = conn.execute(
            """
            SELECT i.iface_id
            FROM t02_interface_name AS i
            JOIN t04_eigrp_processes AS p ON p.host = i.host
            WHERE p.eigrp_id = ? AND i.interface_name = ?
            LIMIT 1;
            """,
            (eigrp_id, db._str_or_none(row.get("interface_name"))),
        ).fetchone()
        if interface is None:
            raise ValueError(
                f"EIGRP interface does not exist for this device: {row.get('interface_name')}"
            )
        conn.execute(
            """
            INSERT INTO t04_router_iface_eigrp (
                iface_id, eigrp_id, bandwidth, delay, hello_interval, hold_time,
                auth_key_chain, summary_ip, summary_mask, split_horizon,
                bandwidth_percent, next_hop_self, bfd, bfd_tx, bfd_rx, bfd_multiplier, sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_apply');
            """,
            (
                interface["iface_id"],
                eigrp_id,
                db._int_or_none(row.get("bandwidth")),
                db._int_or_none(row.get("delay")),
                db._int_or_none(row.get("hello_interval")),
                db._int_or_none(row.get("hold_time")),
                db._str_or_none(row.get("auth_key_chain")),
                db._str_or_none(row.get("summary_ip")),
                db._str_or_none(row.get("summary_mask")),
                db._bool_int(row.get("split_horizon")),
                db._int_or_none(row.get("bandwidth_percent")),
                db._bool_int(row.get("next_hop_self")),
                db._bool_int(row.get("bfd")),
                db._int_or_none(row.get("bfd_tx")),
                db._int_or_none(row.get("bfd_rx")),
                db._int_or_none(row.get("bfd_multiplier")),
            ),
        )
        return

    if table == "t04_eigrp_passive_interfaces":
        conn.execute(
            """
            INSERT INTO t04_eigrp_passive_interfaces (eigrp_id, interface_name, mode, sync_status)
            VALUES (?, ?, ?, 'pending_apply');
            """,
            (eigrp_id, db._str_or_none(row.get("interface_name")), db._str_or_none(row.get("mode")) or "passive"),
        )
        return

    if table == "t04_eigrp_distribute_lists":
        conn.execute(
            """
            INSERT INTO t04_eigrp_distribute_lists (eigrp_id, list_name, direction, interface_name, sync_status)
            VALUES (?, ?, ?, ?, 'pending_apply');
            """,
            (
                eigrp_id,
                db._str_or_none(row.get("list_name")),
                db._str_or_none(row.get("direction")) or "in",
                db._str_or_none(row.get("interface_name")),
            ),
        )
        return

    if table == "t04_eigrp_offset_lists":
        conn.execute(
            """
            INSERT INTO t04_eigrp_offset_lists (eigrp_id, list_name, direction, value, interface_name, sync_status)
            VALUES (?, ?, ?, ?, ?, 'pending_apply');
            """,
            (
                eigrp_id,
                db._str_or_none(row.get("list_name")),
                db._str_or_none(row.get("direction")) or "in",
                db._int_or_none(row.get("value")),
                db._str_or_none(row.get("interface_name")),
            ),
        )
        return

    if table == "t04_eigrp_redistribute":
        conn.execute(
            """
            INSERT INTO t04_eigrp_redistribute (
                eigrp_id, protocol, route_map, metric_bw, metric_delay,
                metric_reliability, metric_load, metric_mtu, sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_apply');
            """,
            (
                eigrp_id,
                db._str_or_none(row.get("protocol")),
                db._str_or_none(row.get("route_map")),
                db._int_or_none(row.get("metric_bw")),
                db._int_or_none(row.get("metric_delay")),
                db._int_or_none(row.get("metric_reliability")),
                db._int_or_none(row.get("metric_load")),
                db._int_or_none(row.get("metric_mtu")),
            ),
        )
        return

    raise ValueError(f"Unsupported child table: {table}")


def update_child_row(conn: sqlite3.Connection, db: Any, row_id: int, table: str, row: dict[str, Any]) -> None:
    if table == "t04_eigrp_networks":
        conn.execute(
            """
            UPDATE t04_eigrp_networks
            SET network = ?, wildcard = ?, interface_name = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (
                db._str_or_none(row.get("network")),
                db._str_or_none(row.get("wildcard")),
                db._str_or_none(row.get("interface_name")),
                row_id,
            ),
        )
        return

    if table == "t04_router_iface_eigrp":
        conn.execute(
            """
            UPDATE t04_router_iface_eigrp
            SET bandwidth = ?, delay = ?, hello_interval = ?, hold_time = ?,
                auth_key_chain = ?, summary_ip = ?, summary_mask = ?, split_horizon = ?,
                bandwidth_percent = ?, next_hop_self = ?, bfd = ?, bfd_tx = ?, bfd_rx = ?,
                bfd_multiplier = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (
                db._int_or_none(row.get("bandwidth")),
                db._int_or_none(row.get("delay")),
                db._int_or_none(row.get("hello_interval")),
                db._int_or_none(row.get("hold_time")),
                db._str_or_none(row.get("auth_key_chain")),
                db._str_or_none(row.get("summary_ip")),
                db._str_or_none(row.get("summary_mask")),
                db._bool_int(row.get("split_horizon")),
                db._int_or_none(row.get("bandwidth_percent")),
                db._bool_int(row.get("next_hop_self")),
                db._bool_int(row.get("bfd")),
                db._int_or_none(row.get("bfd_tx")),
                db._int_or_none(row.get("bfd_rx")),
                db._int_or_none(row.get("bfd_multiplier")),
                row_id,
            ),
        )
        return

    if table == "t04_eigrp_passive_interfaces":
        conn.execute(
            "UPDATE t04_eigrp_passive_interfaces SET interface_name = ?, mode = ?, sync_status = 'pending_apply' WHERE id = ?;",
            (db._str_or_none(row.get("interface_name")), db._str_or_none(row.get("mode")) or "passive", row_id),
        )
        return

    if table == "t04_eigrp_distribute_lists":
        conn.execute(
            """
            UPDATE t04_eigrp_distribute_lists
            SET list_name = ?, direction = ?, interface_name = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (
                db._str_or_none(row.get("list_name")),
                db._str_or_none(row.get("direction")) or "in",
                db._str_or_none(row.get("interface_name")),
                row_id,
            ),
        )
        return

    if table == "t04_eigrp_offset_lists":
        conn.execute(
            """
            UPDATE t04_eigrp_offset_lists
            SET list_name = ?, direction = ?, value = ?, interface_name = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (
                db._str_or_none(row.get("list_name")),
                db._str_or_none(row.get("direction")) or "in",
                db._int_or_none(row.get("value")),
                db._str_or_none(row.get("interface_name")),
                row_id,
            ),
        )
        return

    if table == "t04_eigrp_redistribute":
        conn.execute(
            """
            UPDATE t04_eigrp_redistribute
            SET protocol = ?, route_map = ?, metric_bw = ?, metric_delay = ?,
                metric_reliability = ?, metric_load = ?, metric_mtu = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (
                db._str_or_none(row.get("protocol")),
                db._str_or_none(row.get("route_map")),
                db._int_or_none(row.get("metric_bw")),
                db._int_or_none(row.get("metric_delay")),
                db._int_or_none(row.get("metric_reliability")),
                db._int_or_none(row.get("metric_load")),
                db._int_or_none(row.get("metric_mtu")),
                row_id,
            ),
        )
        return

    raise ValueError(f"Unsupported child table: {table}")
