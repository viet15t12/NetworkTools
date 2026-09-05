from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from ..common import log_db_error, normalize_host


def get_ospf_routing(db: Any, host: str) -> dict[str, Any]:
    host = normalize_host(host)
    if not host:
        return {"ok": False, "message": "Host is empty", "processes": []}

    try:
        with closing(db._connect()) as conn:
            process_rows = conn.execute(
                """
                SELECT ospf_id, process_id, router_id, reference_bandwidth,
                       passive_default, default_originate, default_originate_always, sync_status
                FROM t04_ospf_processes
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY ospf_id ASC;
                """,
                (host,),
            ).fetchall()

            processes: list[dict[str, Any]] = []
            for process_row in process_rows:
                ospf_id = process_row["ospf_id"]
                process = dict(process_row)
                process["networks"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, network, wildcard, area, sync_status
                        FROM t04_ospf_networks
                        WHERE ospf_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (ospf_id,),
                    ).fetchall()
                )

                distance = conn.execute(
                    """
                    SELECT external, intra_area, inter_area, sync_status
                    FROM t04_ospf_distance
                    WHERE ospf_id = ? AND sync_status != 'pending_delete'
                    LIMIT 1;
                    """,
                    (ospf_id,),
                ).fetchone()
                process["distance"] = dict(distance) if distance else {}

                area_rows = conn.execute(
                    """
                    SELECT id, area_id, area_type, no_summary, authentication, sync_status
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
                            SELECT id, ip, mask, advertise, cost, sync_status
                            FROM t04_ospf_area_ranges
                            WHERE area_db_id = ? AND sync_status != 'pending_delete'
                            ORDER BY id ASC;
                            """,
                            (area_row["id"],),
                        ).fetchall()
                    )
                    areas.append(area)
                process["areas"] = areas

                process["redistribute"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, protocol, process_id, subnets, metric, metric_type, route_map, sync_status
                        FROM t04_ospf_redistribute
                        WHERE ospf_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (ospf_id,),
                    ).fetchall()
                )
                process["passive_interfaces"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, interface_name, passive, sync_status
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
                           lsa_delay, lsa_min_delay, lsa_max_delay, sync_status
                    FROM t04_ospf_tuning
                    WHERE ospf_id = ? AND sync_status != 'pending_delete'
                    LIMIT 1;
                    """,
                    (ospf_id,),
                ).fetchone()
                process["tuning"] = dict(tuning) if tuning else {}
                process["interface_settings"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT r.id, i.interface_name, r.area, r.cost, r.priority,
                               r.hello_interval, r.dead_interval, r.mtu_ignore, r.bfd,
                               r.network_type, r.auth_type, r.auth_key, r.sync_status
                        FROM t04_router_iface_ospf AS r
                        JOIN t02_interface_name AS i ON i.iface_id = r.iface_id
                        WHERE r.ospf_id = ? AND r.sync_status != 'pending_delete'
                        ORDER BY r.id ASC;
                        """,
                        (ospf_id,),
                    ).fetchall()
                )
                processes.append(process)

        return {"ok": True, "message": "Loaded OSPF routing", "processes": processes}
    except sqlite3.Error as exc:
        log_db_error("getOspfRouting", exc)
        return {"ok": False, "message": str(exc), "processes": []}
