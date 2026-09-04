from __future__ import annotations

from contextlib import closing
from typing import Any

from .common import text


def get_port_counters(db: Any, host: str) -> list[dict[str, Any]]:
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT i.if_name, i.oper_status,
                   COALESCE(m.in_octets, 0) AS in_octets,
                   COALESCE(m.out_octets, 0) AS out_octets,
                   COALESCE(m.in_errors, 0) AS in_errors,
                   COALESCE(m.out_errors, 0) AS out_errors,
                   COALESCE(m.in_discards, 0) AS in_discards,
                   COALESCE(m.out_discards, 0) AS out_discards,
                   COALESCE(m.last_flap, 'never') AS last_flap,
                   COALESCE(m.polled_at, '') AS polled_at
            FROM t06_interface_l2 AS i
            LEFT JOIN t06_iface_monitor AS m ON m.iface_id = i.id
            WHERE i.host = ?
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            (text(host),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_mac_table(db: Any, host: str) -> list[dict[str, Any]]:
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.mac_addr, m.vlan_id, i.if_name,
                   m.mac_type, m.learned_at
            FROM t06_iface_mac_table AS m
            JOIN t06_interface_l2 AS i ON i.id = m.iface_id
            WHERE i.host = ?
            ORDER BY m.vlan_id, m.mac_addr COLLATE NOCASE;
            """,
            (text(host),),
        ).fetchall()
    return [dict(row) for row in rows]
