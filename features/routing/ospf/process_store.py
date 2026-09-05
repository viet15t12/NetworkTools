from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from typing import Any

from .common import as_dict, as_list, process_action_cfg


OSPF_PASSIVE_IFACE_NAME_COLUMN = "interface_name"


def reset_ospf_process_children(conn: sqlite3.Connection, ospf_id: int) -> None:
    for table in (
        "t04_ospf_networks",
        "t04_ospf_distance",
        "t04_ospf_areas",
        "t04_ospf_redistribute",
        "t04_ospf_passive_interfaces",
        "t04_ospf_tuning",
        "t04_router_iface_ospf",
    ):
        conn.execute(f"UPDATE {table} SET sync_status = 'pending_delete' WHERE ospf_id = ?;", (ospf_id,))
    conn.execute(
        """
        UPDATE t04_ospf_area_ranges
        SET sync_status = 'pending_delete'
        WHERE area_db_id IN (
            SELECT id FROM t04_ospf_areas WHERE ospf_id = ?
        );
        """,
        (ospf_id,),
    )


def archive_ospf_process(conn: sqlite3.Connection, ospf_id: int) -> None:
    conn.execute("UPDATE t04_ospf_processes SET sync_status = 'pending_delete' WHERE ospf_id = ?;", (ospf_id,))
    reset_ospf_process_children(conn, ospf_id)


def _upsert_ospf_network(conn: sqlite3.Connection, ospf_id: int, network: str | None, wildcard: str | None, area: int) -> None:
    if not network or not wildcard:
        return
    conn.execute(
        """
        INSERT INTO t04_ospf_networks (ospf_id, network, wildcard, area, sync_status)
        VALUES (?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(ospf_id, network, wildcard, area) DO UPDATE SET
            sync_status = 'pending_apply';
        """,
        (ospf_id, network, wildcard, area),
    )


def _upsert_ospf_distance(
    conn: sqlite3.Connection,
    ospf_id: int,
    external: int | None,
    intra_area: int | None,
    inter_area: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO t04_ospf_distance (ospf_id, external, intra_area, inter_area, sync_status)
        VALUES (?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(ospf_id) DO UPDATE SET
            external = excluded.external,
            intra_area = excluded.intra_area,
            inter_area = excluded.inter_area,
            sync_status = 'pending_apply';
        """,
        (ospf_id, external, intra_area, inter_area),
    )


def _upsert_ospf_area(
    conn: sqlite3.Connection,
    ospf_id: int,
    area_id: int,
    area_type: str,
    no_summary: int,
    authentication: str | None,
) -> int:
    conn.execute(
        """
        INSERT INTO t04_ospf_areas (
            ospf_id, area_id, area_type, no_summary, authentication, sync_status
        )
        VALUES (?, ?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(ospf_id, area_id) DO UPDATE SET
            area_type = excluded.area_type,
            no_summary = excluded.no_summary,
            authentication = excluded.authentication,
            sync_status = 'pending_apply';
        """,
        (ospf_id, area_id, area_type, no_summary, authentication),
    )
    row = conn.execute(
        """
        SELECT id
        FROM t04_ospf_areas
        WHERE ospf_id = ? AND area_id = ?
        LIMIT 1;
        """,
        (ospf_id, area_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"OSPF area {area_id} could not be saved")
    return int(row["id"])


def _upsert_ospf_area_range(
    conn: sqlite3.Connection,
    area_db_id: int,
    ip: str | None,
    mask: str | None,
    advertise: int,
    cost: int | None,
) -> None:
    if not ip or not mask:
        return
    conn.execute(
        """
        INSERT INTO t04_ospf_area_ranges (area_db_id, ip, mask, advertise, cost, sync_status)
        VALUES (?, ?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(area_db_id, ip, mask) DO UPDATE SET
            advertise = excluded.advertise,
            cost = excluded.cost,
            sync_status = 'pending_apply';
        """,
        (area_db_id, ip, mask, advertise, cost),
    )


def _upsert_ospf_redistribute(
    conn: sqlite3.Connection,
    ospf_id: int,
    protocol: str,
    process_id: int | None,
    subnets: int,
    metric: int | None,
    metric_type: int | None,
    route_map: str | None,
) -> None:
    row = conn.execute(
        """
        SELECT id
        FROM t04_ospf_redistribute
        WHERE ospf_id = ?
          AND protocol = ?
          AND (
            (process_id IS NULL AND ? IS NULL)
            OR process_id = ?
          )
        ORDER BY id ASC
        LIMIT 1;
        """,
        (ospf_id, protocol, process_id, process_id),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE t04_ospf_redistribute
            SET subnets = ?, metric = ?, metric_type = ?, route_map = ?, sync_status = 'pending_apply'
            WHERE id = ?;
            """,
            (subnets, metric, metric_type, route_map, row["id"]),
        )
        return
    conn.execute(
        """
        INSERT INTO t04_ospf_redistribute (
            ospf_id, protocol, process_id, subnets, metric, metric_type, route_map, sync_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_apply');
        """,
        (ospf_id, protocol, process_id, subnets, metric, metric_type, route_map),
    )


def _upsert_ospf_passive_interface(
    conn: sqlite3.Connection,
    ospf_id: int,
    interface_name: str,
    passive: int,
) -> None:
    conn.execute(
        f"""
        INSERT INTO t04_ospf_passive_interfaces (
            ospf_id, {OSPF_PASSIVE_IFACE_NAME_COLUMN}, passive, sync_status
        )
        VALUES (?, ?, ?, 'pending_apply')
        ON CONFLICT(ospf_id, {OSPF_PASSIVE_IFACE_NAME_COLUMN}) DO UPDATE SET
            passive = excluded.passive,
            sync_status = 'pending_apply';
        """,
        (ospf_id, interface_name, passive),
    )


def _upsert_ospf_tuning(
    conn: sqlite3.Connection,
    ospf_id: int,
    tuning_values: tuple[int | None, int | None, int | None, int | None, int | None, int | None, int | None, int | None],
) -> None:
    conn.execute(
        """
        INSERT INTO t04_ospf_tuning (
            ospf_id, maximum_paths, max_lsa, spf_delay, spf_min_delay, spf_max_delay,
            lsa_delay, lsa_min_delay, lsa_max_delay, sync_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(ospf_id) DO UPDATE SET
            maximum_paths = excluded.maximum_paths,
            max_lsa = excluded.max_lsa,
            spf_delay = excluded.spf_delay,
            spf_min_delay = excluded.spf_min_delay,
            spf_max_delay = excluded.spf_max_delay,
            lsa_delay = excluded.lsa_delay,
            lsa_min_delay = excluded.lsa_min_delay,
            lsa_max_delay = excluded.lsa_max_delay,
            sync_status = 'pending_apply';
        """,
        (ospf_id, *tuning_values),
    )


def _upsert_ospf_interface_setting(
    conn: sqlite3.Connection,
    ospf_id: int,
    interface_name: str,
    area: int,
    cost: int | None,
    priority: int,
    hello_interval: int | None,
    dead_interval: int | None,
    mtu_ignore: int,
    bfd: int,
    network_type: str | None,
    auth_type: str | None,
    auth_key: str | None,
) -> None:
    interface = conn.execute(
        """
        SELECT i.iface_id
        FROM t02_interface_name AS i
        JOIN t04_ospf_processes AS p ON p.host = i.host
        WHERE p.ospf_id = ? AND i.interface_name = ?
        LIMIT 1;
        """,
        (ospf_id, interface_name),
    ).fetchone()
    if interface is None:
        raise ValueError(f"OSPF interface does not exist for this device: {interface_name}")

    conn.execute(
        """
        INSERT INTO t04_router_iface_ospf (
            iface_id, ospf_id, area, cost, priority, hello_interval, dead_interval,
            mtu_ignore, bfd, network_type, auth_type, auth_key, sync_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_apply')
        ON CONFLICT(iface_id, ospf_id) DO UPDATE SET
            area = excluded.area,
            cost = excluded.cost,
            priority = excluded.priority,
            hello_interval = excluded.hello_interval,
            dead_interval = excluded.dead_interval,
            mtu_ignore = excluded.mtu_ignore,
            bfd = excluded.bfd,
            network_type = excluded.network_type,
            auth_type = excluded.auth_type,
            auth_key = excluded.auth_key,
            sync_status = 'pending_apply';
        """,
        (
            interface["iface_id"],
            ospf_id,
            area,
            cost,
            priority,
            hello_interval,
            dead_interval,
            mtu_ignore,
            bfd,
            network_type,
            auth_type,
            auth_key,
        ),
    )


def insert_ospf_process(conn: sqlite3.Connection, db: Any, host: str, process: dict[str, Any]) -> int:
    process_id = db._int_or_none(process.get("process_id"))
    if process_id is None:
        raise ValueError("OSPF process_id is required")

    existing = conn.execute(
        """
        SELECT ospf_id, process_id, router_id, reference_bandwidth,
               passive_default, default_originate, default_originate_always,
               action_Cfg
        FROM t04_ospf_processes
        WHERE host = ? AND process_id = ?
        ORDER BY ospf_id ASC
        LIMIT 1;
        """,
        (host, process_id),
    ).fetchone()

    if existing is not None:
        ospf_id = existing["ospf_id"]
        action_cfg = process_action_cfg(dict(existing), process)
        conn.execute(
            """
            UPDATE t04_ospf_processes
            SET router_id = ?,
                reference_bandwidth = ?,
                passive_default = ?,
                default_originate = ?,
                default_originate_always = ?,
                action_Cfg = ?,
                sync_status = 'pending_apply'
            WHERE ospf_id = ?;
            """,
            (
                db._str_or_none(process.get("router_id")),
                db._int_or_none(process.get("reference_bandwidth")),
                db._bool_int(process.get("passive_default")),
                db._bool_int(process.get("default_originate")),
                db._bool_int(process.get("default_originate_always")),
                action_cfg,
                ospf_id,
            ),
        )
        reset_ospf_process_children(conn, ospf_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO t04_ospf_processes (
                host, process_id, router_id, reference_bandwidth,
                passive_default, default_originate, default_originate_always,
                action_Cfg, sync_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, '1111', 'pending_apply');
            """,
            (
                host,
                process_id,
                db._str_or_none(process.get("router_id")),
                db._int_or_none(process.get("reference_bandwidth")),
                db._bool_int(process.get("passive_default")),
                db._bool_int(process.get("default_originate")),
                db._bool_int(process.get("default_originate_always")),
            ),
        )
        ospf_id = cur.lastrowid

    for network_value in as_list(db, process.get("networks")):
        network = as_dict(db, network_value)
        _upsert_ospf_network(
            conn,
            ospf_id,
            db._str_or_none(network.get("network")),
            db._str_or_none(network.get("wildcard")),
            db._int_or_zero(network.get("area")),
        )

    distance = as_dict(db, process.get("distance"))
    if distance:
        _upsert_ospf_distance(
            conn,
            ospf_id,
            db._int_or_none(distance.get("external")),
            db._int_or_none(distance.get("intra_area")),
            db._int_or_none(distance.get("inter_area")),
        )

    for area_value in as_list(db, process.get("areas")):
        area = as_dict(db, area_value)
        area_db_id = _upsert_ospf_area(
            conn,
            ospf_id,
            db._int_or_zero(area.get("area_id")),
            db._str_or_none(area.get("area_type")) or "normal",
            db._bool_int(area.get("no_summary")),
            db._str_or_none(area.get("authentication")),
        )
        for range_value in as_list(db, area.get("ranges")):
            range_row = as_dict(db, range_value)
            _upsert_ospf_area_range(
                conn,
                area_db_id,
                db._str_or_none(range_row.get("ip")),
                db._str_or_none(range_row.get("mask")),
                db._bool_int(range_row.get("advertise", True)),
                db._int_or_none(range_row.get("cost")),
            )

    for redist_value in as_list(db, process.get("redistribute")):
        redist = as_dict(db, redist_value)
        protocol = db._str_or_none(redist.get("protocol"))
        if not protocol:
            continue
        _upsert_ospf_redistribute(
            conn,
            ospf_id,
            protocol,
            db._int_or_none(redist.get("process_id")),
            db._bool_int(redist.get("subnets", True)),
            db._int_or_none(redist.get("metric")),
            db._int_or_none(redist.get("metric_type")),
            db._str_or_none(redist.get("route_map")),
        )

    for passive_value in as_list(db, process.get("passive_interfaces")):
        passive = as_dict(db, passive_value)
        iface = db._str_or_none(passive.get("interface_name"))
        if not iface:
            continue
        _upsert_ospf_passive_interface(conn, ospf_id, iface, db._bool_int(passive.get("passive", True)))

    tuning = as_dict(db, process.get("tuning"))
    if tuning:
        _upsert_ospf_tuning(
            conn,
            ospf_id,
            (
                db._int_or_none(tuning.get("maximum_paths")),
                db._int_or_none(tuning.get("max_lsa")),
                db._int_or_none(tuning.get("spf_delay")),
                db._int_or_none(tuning.get("spf_min_delay")),
                db._int_or_none(tuning.get("spf_max_delay")),
                db._int_or_none(tuning.get("lsa_delay")),
                db._int_or_none(tuning.get("lsa_min_delay")),
                db._int_or_none(tuning.get("lsa_max_delay")),
            ),
        )

    for iface_value in as_list(db, process.get("interface_settings")):
        iface = as_dict(db, iface_value)
        iface_name = db._str_or_none(iface.get("interface_name"))
        if not iface_name:
            continue
        _upsert_ospf_interface_setting(
            conn,
            ospf_id,
            iface_name,
            db._int_or_zero(iface.get("area")),
            db._int_or_none(iface.get("cost")),
            db._int_or_none(iface.get("priority")) if iface.get("priority") not in (None, "") else 1,
            db._int_or_none(iface.get("hello_interval")),
            db._int_or_none(iface.get("dead_interval")),
            db._bool_int(iface.get("mtu_ignore")),
            db._bool_int(iface.get("bfd")),
            db._str_or_none(iface.get("network_type")),
            db._str_or_none(iface.get("auth_type")),
            db._str_or_none(iface.get("auth_key")),
        )

    return ospf_id
