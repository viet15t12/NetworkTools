"""Collect pending router-interface rows into device-neutral push tasks."""

from __future__ import annotations

from typing import Any

from .common import db_connection


_PROFILE_TABLES = {
    "l3": "t02_router_iface_l3",
    "tunnel": "t02_router_iface_tunnel",
    "wan": "t02_router_iface_wan",
}


def _row_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _load_profile(connection: Any, table: str, iface_id: int) -> dict[str, Any] | None:
    return _row_dict(
        connection.execute(
            f"SELECT * FROM {table} WHERE iface_id = ?;",
            (iface_id,),
        ).fetchone()
    )


def collect_interface_tasks(db: Any, host: str) -> list[dict[str, Any]]:
    """Return one independently trackable task for every pending interface."""
    host = (host or "").strip()
    if not host:
        return []

    with db_connection(db) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT i.*
            FROM t02_interface_name AS i
            LEFT JOIN t02_router_iface_l3 AS l ON l.iface_id = i.iface_id
            LEFT JOIN t02_router_iface_tunnel AS t ON t.iface_id = i.iface_id
            LEFT JOIN t02_router_iface_wan AS w ON w.iface_id = i.iface_id
            LEFT JOIN t02_router_iface_subif AS s
              ON s.host = i.host AND s.subif_name = i.interface_name
            WHERE i.host = ?
              AND (
                    COALESCE(i.sync_status, 'pending_apply') IN ('pending_apply', 'pending_delete')
                 OR (l.iface_id IS NOT NULL AND COALESCE(l.sync_status, 'pending_apply') IN ('pending_apply', 'pending_delete'))
                 OR (t.iface_id IS NOT NULL AND COALESCE(t.sync_status, 'pending_apply') IN ('pending_apply', 'pending_delete'))
                 OR (w.iface_id IS NOT NULL AND COALESCE(w.sync_status, 'pending_apply') IN ('pending_apply', 'pending_delete'))
                 OR (s.id IS NOT NULL AND COALESCE(s.sync_status, 'pending_apply') IN ('pending_apply', 'pending_delete'))
              )
            ORDER BY i.interface_name COLLATE NOCASE;
            """,
            (host,),
        ).fetchall()

        tasks: list[dict[str, Any]] = []
        for row in rows:
            base = dict(row)
            iface_id = int(base["iface_id"])
            profiles = {
                name: _load_profile(connection, table, iface_id)
                for name, table in _PROFILE_TABLES.items()
            }
            profiles["subinterface"] = _row_dict(
                connection.execute(
                    "SELECT * FROM t02_router_iface_subif WHERE host = ? AND subif_name = ?",
                    (host, base["interface_name"]),
                ).fetchone()
            )
            active_kind = next(
                (
                    name
                    for name in ("subinterface", "tunnel", "wan", "l3")
                    if profiles[name] is not None
                    and profiles[name].get("sync_status") != "pending_delete"
                ),
                None,
            )
            removed_profiles = {
                name: profile
                for name, profile in profiles.items()
                if profile is not None and profile.get("sync_status") == "pending_delete"
            }
            tasks.append(
                {
                    "target": {"ip": host},
                    "module": "interface",
                    "action": "remove"
                    if base.get("sync_status") == "pending_delete"
                    else "setup",
                    "interface": base,
                    "profile_kind": active_kind,
                    "profile": profiles.get(active_kind) if active_kind else None,
                    "removed_profiles": removed_profiles,
                    "tracking": {
                        "iface_id": iface_id,
                        "base_pending": base.get("sync_status") in (
                            None,
                            "pending_apply",
                            "pending_delete",
                        ),
                        "profile_states": {
                            name: str(profile.get("sync_status") or "pending_apply")
                            for name, profile in profiles.items()
                            if profile is not None
                        },
                    },
                }
            )
    return tasks


__all__ = ["collect_interface_tasks"]
