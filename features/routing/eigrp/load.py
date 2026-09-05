from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from ..common import log_db_error, normalize_host


def get_eigrp_routing(db: Any, host: str) -> dict[str, Any]:
    host = normalize_host(host)
    if not host:
        return {"ok": False, "message": "Host is empty", "processes": []}

    try:
        with closing(db._connect()) as conn:
            key_chains = db._dict_rows(
                conn.execute(
                    """
                    SELECT id, chain_name, key_id, key_string, accept_lifetime, send_lifetime, sync_status
                    FROM t04_eigrp_key_chains
                    WHERE host = ? AND sync_status != 'pending_delete'
                    ORDER BY id ASC;
                    """,
                    (host,),
                ).fetchall()
            )
            process_rows = conn.execute(
                """
                SELECT eigrp_id, as_number, router_id, timers_active_time, bfd_all_interfaces,
                       auto_summary, passive_default, metric_weights, distance_internal, distance_external,
                       variance, maximum_paths, stub_enabled, stub_options, stub_leak_map,
                       action, action_Cfg, sync_status
                FROM t04_eigrp_processes
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY eigrp_id ASC;
                """,
                (host,),
            ).fetchall()

            processes: list[dict[str, Any]] = []
            for process_row in process_rows:
                eigrp_id = process_row["eigrp_id"]
                process = dict(process_row)
                process["networks"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, network, wildcard, interface_name, sync_status
                        FROM t04_eigrp_networks
                        WHERE eigrp_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["interface_settings"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT r.id, i.interface_name, r.bandwidth, r.delay,
                               r.hello_interval, r.hold_time, r.auth_key_chain,
                               r.summary_ip, r.summary_mask, r.split_horizon,
                               r.bandwidth_percent, r.next_hop_self, r.bfd,
                               r.bfd_tx, r.bfd_rx, r.bfd_multiplier, r.sync_status
                        FROM t04_router_iface_eigrp AS r
                        JOIN t02_interface_name AS i ON i.iface_id = r.iface_id
                        WHERE r.eigrp_id = ? AND r.sync_status != 'pending_delete'
                        ORDER BY r.id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["passive_interfaces"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, interface_name, mode, sync_status
                        FROM t04_eigrp_passive_interfaces
                        WHERE eigrp_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["distribute_lists"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, list_name, direction, interface_name, sync_status
                        FROM t04_eigrp_distribute_lists
                        WHERE eigrp_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["offset_lists"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, list_name, direction, value, interface_name, sync_status
                        FROM t04_eigrp_offset_lists
                        WHERE eigrp_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["redistribute"] = db._dict_rows(
                    conn.execute(
                        """
                        SELECT id, protocol, route_map, metric_bw, metric_delay,
                               metric_reliability, metric_load, metric_mtu, sync_status
                        FROM t04_eigrp_redistribute
                        WHERE eigrp_id = ? AND sync_status != 'pending_delete'
                        ORDER BY id ASC;
                        """,
                        (eigrp_id,),
                    ).fetchall()
                )
                process["key_chains"] = key_chains
                processes.append(process)

        return {"ok": True, "message": "Loaded EIGRP routing", "processes": processes}
    except sqlite3.Error as exc:
        log_db_error("getEigrpRouting", exc)
        return {"ok": False, "message": str(exc), "processes": []}
