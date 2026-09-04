from __future__ import annotations

import sqlite3
from typing import Any

from .common import as_dict, as_list, bool_int_value, int_or_zero_value, network_key, payload_networks, text


def sync_ospf_networks(conn: sqlite3.Connection, db: Any, ospf_id: int, process: dict[str, Any]) -> None:
    existing_rows = conn.execute(
        """
        SELECT id, network, wildcard, area
        FROM t04_ospf_networks
        WHERE ospf_id = ? AND sync_status != 'pending_delete';
        """,
        (ospf_id,),
    ).fetchall()
    existing = {network_key(dict(row)): row["id"] for row in existing_rows}
    submitted = payload_networks(db, process)

    for key, row_id in existing.items():
        if key not in submitted:
            conn.execute("UPDATE t04_ospf_networks SET sync_status = 'pending_delete' WHERE id = ?;", (row_id,))

    for key in submitted:
        if key not in existing:
            conn.execute(
                """
                INSERT INTO t04_ospf_networks (ospf_id, network, wildcard, area, sync_status)
                VALUES (?, ?, ?, ?, 'pending_apply')
                ON CONFLICT(ospf_id, network, wildcard, area) DO UPDATE SET
                    sync_status = 'pending_apply';
                """,
                (ospf_id, key[0], key[1], key[2]),
            )


def load_process_for_compare(conn: sqlite3.Connection, db: Any, ospf_id: int) -> dict[str, Any] | None:
    process = conn.execute(
        """
        SELECT ospf_id, process_id, router_id, reference_bandwidth,
               passive_default, default_originate, default_originate_always,
               action_Cfg
        FROM t04_ospf_processes
        WHERE ospf_id = ? AND sync_status != 'pending_delete'
        LIMIT 1;
        """,
        (ospf_id,),
    ).fetchone()
    if process is None:
        return None

    data = dict(process)
    data["networks"] = db._dict_rows(
        conn.execute(
            """
            SELECT network, wildcard, area
            FROM t04_ospf_networks
            WHERE ospf_id = ? AND sync_status != 'pending_delete'
            ORDER BY id ASC;
            """,
            (ospf_id,),
        ).fetchall()
    )
    distance = conn.execute(
        """
        SELECT external, intra_area, inter_area
        FROM t04_ospf_distance
        WHERE ospf_id = ? AND sync_status != 'pending_delete'
        LIMIT 1;
        """,
        (ospf_id,),
    ).fetchone()
    data["distance"] = dict(distance) if distance else {}

    area_rows = conn.execute(
        """
        SELECT id, area_id, area_type, no_summary, authentication
        FROM t04_ospf_areas
        WHERE ospf_id = ? AND sync_status != 'pending_delete'
        ORDER BY id ASC;
        """,
        (ospf_id,),
    ).fetchall()
    areas: list[dict[str, Any]] = []
    for area_row in area_rows:
        area = dict(area_row)
        area["ranges"] = db._dict_rows(
            conn.execute(
                """
                SELECT ip, mask, advertise, cost
                FROM t04_ospf_area_ranges
                WHERE area_db_id = ? AND sync_status != 'pending_delete'
                ORDER BY id ASC;
                """,
                (area_row["id"],),
            ).fetchall()
        )
        areas.append(area)
    data["areas"] = areas

    data["redistribute"] = db._dict_rows(
        conn.execute(
            """
            SELECT protocol, process_id, subnets, metric, metric_type, route_map
            FROM t04_ospf_redistribute
            WHERE ospf_id = ? AND sync_status != 'pending_delete'
            ORDER BY id ASC;
            """,
            (ospf_id,),
        ).fetchall()
    )
    data["passive_interfaces"] = db._dict_rows(
        conn.execute(
            """
            SELECT interface_name, passive
            FROM t04_ospf_passive_interfaces
            WHERE ospf_id = ? AND sync_status != 'pending_delete'
            ORDER BY id ASC;
            """,
            (ospf_id,),
        ).fetchall()
    )
    tuning = conn.execute(
        """
        SELECT maximum_paths, max_lsa, spf_delay, spf_min_delay, spf_max_delay,
               lsa_delay, lsa_min_delay, lsa_max_delay
        FROM t04_ospf_tuning
        WHERE ospf_id = ? AND sync_status != 'pending_delete'
        LIMIT 1;
        """,
        (ospf_id,),
    ).fetchone()
    data["tuning"] = dict(tuning) if tuning else {}
    data["interface_settings"] = db._dict_rows(
        conn.execute(
            """
            SELECT i.interface_name, r.area, r.cost, r.priority,
                   r.hello_interval, r.dead_interval, r.mtu_ignore, r.bfd,
                   r.network_type, r.auth_type, r.auth_key
            FROM t04_router_iface_ospf AS r
            JOIN t02_interface_name AS i ON i.iface_id = r.iface_id
            WHERE r.ospf_id = ? AND r.sync_status != 'pending_delete'
            ORDER BY r.id ASC;
            """,
            (ospf_id,),
        ).fetchall()
    )
    return data


def is_blank_ospf_process_submission(db: Any, process: dict[str, Any]) -> bool:
    if db._int_or_none(process.get("process_id")) is not None:
        return False
    if text(process.get("router_id")):
        return False
    if int_or_zero_value(process.get("reference_bandwidth")) > 0:
        return False
    if bool_int_value(process.get("passive_default")):
        return False
    if bool_int_value(process.get("default_originate")):
        return False
    if bool_int_value(process.get("default_originate_always")):
        return False
    if any(text(as_dict(db, row).get("network")) or text(as_dict(db, row).get("wildcard")) for row in as_list(db, process.get("networks"))):
        return False
    if as_dict(db, process.get("distance")):
        return False
    if as_dict(db, process.get("tuning")):
        return False
    if as_list(db, process.get("areas")):
        return False
    if as_list(db, process.get("redistribute")):
        return False
    if as_list(db, process.get("passive_interfaces")):
        return False
    if as_list(db, process.get("interface_settings")):
        return False
    return True


def describe_process_submission(db: Any, process: dict[str, Any], index: int) -> str:
    return (
        f"submission #{index}: "
        f"ospf_id={process.get('ospf_id')!r}, "
        f"process_id={process.get('process_id')!r}, "
        f"router_id={text(process.get('router_id'))!r}, "
        f"reference_bandwidth={process.get('reference_bandwidth')!r}, "
        f"networks={len(as_list(db, process.get('networks')))}"
    )
