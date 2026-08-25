"""Read pending FHRP member tasks without performing device I/O."""

from __future__ import annotations

from contextlib import closing
from typing import Any


OPTION_TABLES = {
    "hsrp": "t08_hsrp_options",
    "vrrp": "t08_vrrp_options",
    "glbp": "t08_glbp_options",
}


def collect_fhrp_tasks(db: Any, host: str) -> list[dict[str, Any]]:
    """Collect one self-contained configuration task per pending member."""
    target = str(host or "").strip()
    if not target:
        return []
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT m.member_id, m.fhrp_id, m.host, m.iface_id,
                   m.interface_kind,
                   m.priority, m.preempt, m.shutdown, m.sync_status,
                   COALESCE(
                       i.interface_name,
                       'Vlan' || CAST(s.vlan_id AS TEXT)
                   ) AS interface_name,
                   g.protocol, g.group_number,
                   g.virtual_ip, g.address_family, g.description
            FROM t08_fhrp_members AS m
            JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
            LEFT JOIN t02_interface_name AS i
              ON m.interface_kind = 'router' AND i.iface_id = m.iface_id
            LEFT JOIN t06_svi_interface AS s
              ON m.interface_kind = 'svi' AND s.id = m.iface_id
            WHERE m.host = ?
              AND m.sync_status IN ('pending_apply', 'pending_delete')
            ORDER BY m.member_id;
            """,
            (target,),
        ).fetchall()
        tasks: list[dict[str, Any]] = []
        for row in rows:
            config = dict(row)
            option_table = OPTION_TABLES[config["protocol"]]
            option = conn.execute(
                f"SELECT * FROM {option_table} WHERE member_id = ?;",
                (config["member_id"],),
            ).fetchone()
            config["options"] = dict(option) if option is not None else {}
            config["tracks"] = [
                dict(track)
                for track in conn.execute(
                    """
                    SELECT track_id, track_object, decrement_value, sync_status
                    FROM t08_fhrp_tracks
                    WHERE member_id = ?
                      AND sync_status IN ('pending_apply', 'pending_delete')
                    ORDER BY track_id;
                    """,
                    (config["member_id"],),
                ).fetchall()
            ]
            tasks.append(
                {
                    "target": {"ip": target},
                    "sub_type": config["protocol"],
                    "action": (
                        "remove"
                        if config["sync_status"] == "pending_delete"
                        else "setup"
                    ),
                    "config": config,
                }
            )
    return tasks
