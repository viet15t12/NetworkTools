"""Read-only helpers for VLAN behavior inside a configured VTP domain."""

from __future__ import annotations

from contextlib import closing
from typing import Any


def vlan_vtp_context(db: Any, host: str) -> dict[str, Any] | None:
    """Return the configured VLAN-database VTP role for one switch."""
    target = str(host or "").strip()
    if not target:
        return None
    with closing(db._connect()) as conn:
        row = conn.execute(
            """
            SELECT d.vtp_domain_id, d.domain_name, m.mode
            FROM t09_vtp_switches AS s
            JOIN t09_vtp_domains AS d
              ON d.vtp_domain_id = s.vtp_domain_id
            JOIN t09_vtp_database_modes AS m
              ON m.vtp_switch_id = s.vtp_switch_id
             AND m.database_type = 'vlan'
            WHERE s.host = ?
            LIMIT 1;
            """,
            (target,),
        ).fetchone()
    return dict(row) if row is not None else None


def vlan_vtp_clients(db: Any, server_host: str) -> list[str]:
    """List client members only when ``server_host`` is this domain's server."""
    target = str(server_host or "").strip()
    if not target:
        return []
    with closing(db._connect()) as conn:
        server = conn.execute(
            """
            SELECT s.vtp_domain_id
            FROM t09_vtp_switches AS s
            JOIN t09_vtp_database_modes AS m
              ON m.vtp_switch_id = s.vtp_switch_id
             AND m.database_type = 'vlan'
            WHERE s.host = ? AND m.mode = 'server'
            LIMIT 1;
            """,
            (target,),
        ).fetchone()
        if server is None:
            return []
        rows = conn.execute(
            """
            SELECT s.host
            FROM t09_vtp_switches AS s
            JOIN t09_vtp_database_modes AS m
              ON m.vtp_switch_id = s.vtp_switch_id
             AND m.database_type = 'vlan'
            WHERE s.vtp_domain_id = ?
              AND s.host <> ?
              AND m.mode = 'client'
            ORDER BY s.host COLLATE NOCASE;
            """,
            (int(server["vtp_domain_id"]), target),
        ).fetchall()
    return [str(row["host"]) for row in rows]


def require_vlan_configuration_owner(db: Any, host: str) -> None:
    """Reject local VLAN desired-state changes owned by a VTP server."""
    context = vlan_vtp_context(db, host)
    if context is not None and str(context["mode"]).lower() == "client":
        raise ValueError(
            f"VLAN configuration is managed by the VTP server for domain "
            f"{context['domain_name']}; this switch is a VTP client"
        )


__all__ = [
    "require_vlan_configuration_owner",
    "vlan_vtp_clients",
    "vlan_vtp_context",
]
