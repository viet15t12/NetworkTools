"""Commit successful router-interface tasks back to pending-state tables."""

from __future__ import annotations

from typing import Any

from .action_bits import EMPTY_ACTION_CFG
from .common import db_connection


_PROFILE_TABLES = {
    "l3": "t02_router_iface_l3",
    "tunnel": "t02_router_iface_tunnel",
    "wan": "t02_router_iface_wan",
}


def mark_interface_task_applied(db: Any, task: dict[str, Any]) -> None:
    """Update only the rows represented by one successfully pushed task."""
    tracking = task["tracking"]
    iface_id = int(tracking["iface_id"])
    with db_connection(db) as connection:
        if task.get("action") == "remove":
            connection.execute(
                "DELETE FROM t02_router_iface_subif WHERE host = ? AND subif_name = ?;",
                (task["target"]["ip"], task["interface"]["interface_name"]),
            )
            connection.execute(
                "DELETE FROM t02_interface_name WHERE iface_id = ?;",
                (iface_id,),
            )
            connection.commit()
            return

        if tracking.get("base_pending"):
            connection.execute(
                "UPDATE t02_interface_name "
                "SET sync_status = 'synchronized', action_Cfg = ? WHERE iface_id = ?;",
                (EMPTY_ACTION_CFG, iface_id),
            )
        for kind, state in tracking.get("profile_states", {}).items():
            if kind == "subinterface":
                if state == "pending_delete":
                    connection.execute(
                        "DELETE FROM t02_router_iface_subif WHERE host = ? AND subif_name = ?",
                        (task["target"]["ip"], task["interface"]["interface_name"]),
                    )
                elif state == "pending_apply":
                    connection.execute(
                        "UPDATE t02_router_iface_subif SET sync_status = 'synchronized' "
                        "WHERE host = ? AND subif_name = ?",
                        (task["target"]["ip"], task["interface"]["interface_name"]),
                    )
                continue
            table = _PROFILE_TABLES.get(kind)
            if table is None:
                continue
            if state == "pending_delete":
                connection.execute(
                    f"DELETE FROM {table} WHERE iface_id = ?;",
                    (iface_id,),
                )
            elif state == "pending_apply":
                if kind == "l3":
                    connection.execute(
                        f"UPDATE {table} SET sync_status = 'synchronized', "
                        "action_Cfg = '00000' WHERE iface_id = ?;",
                        (iface_id,),
                    )
                else:
                    connection.execute(
                        f"UPDATE {table} SET sync_status = 'synchronized' WHERE iface_id = ?;",
                        (iface_id,),
                    )
        connection.commit()


__all__ = ["mark_interface_task_applied"]
