"""Build granular View/Push tasks for switch and routed interfaces."""

from __future__ import annotations

from contextlib import closing
from typing import Any, Callable

from .commands import render_commands


TaskFactory = Callable[..., dict[str, Any]]


def build_interface_tasks(
    db: Any, host: str, task_factory: TaskFactory
) -> list[dict[str, Any]]:
    """Return pending interface tasks without excluding Layer 3 switch ports.

    A disabled Port Security row is folded into a trunk/routed transition so
    IOS receives the removal command before the mode change.  Its lifecycle is
    tracked in the same task and cannot remain hidden in ``pending_apply``.
    """
    with closing(db._connect()) as conn:
        interfaces = conn.execute(
            """
            SELECT i.id, i.if_name, i.description, i.mode, i.admin_status,
                   i.speed, i.duplex, a.access_vlan, a.voice_vlan,
                   t.allowed_vlans, t.native_vlan, t.encapsulation,
                   t.pruning_vlans, i.success,
                   ps.iface_id AS port_security_id,
                   ps.enabled AS port_security_enabled,
                   ps.success AS port_security_success
            FROM t06_interface_l2 AS i
            LEFT JOIN t06_iface_access AS a ON a.iface_id = i.id
            LEFT JOIN t06_iface_trunk AS t ON t.iface_id = i.id
            LEFT JOIN t06_iface_port_security AS ps ON ps.iface_id = i.id
            WHERE i.host = ? AND (
                i.success IN ('pending_apply','pending_delete') OR i.success IS NULL
            )
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            (host,),
        ).fetchall()
        stp_interfaces = conn.execute(
            """
            SELECT i.if_name, i.mode, s.portfast, s.bpduguard, s.bpdufilter,
                   s.root_guard, s.loop_guard
            FROM t06_interface_l2 AS i
            JOIN t06_iface_stp AS s ON s.iface_id = i.id
            WHERE i.host = ? AND i.mode <> 'routed' AND (
                i.success IN ('pending_apply','pending_delete') OR i.success IS NULL
            );
            """,
            (host,),
        ).fetchall()

    stp_by_name = {str(row["if_name"]): dict(row) for row in stp_interfaces}
    tasks: list[dict[str, Any]] = []
    for source in interfaces:
        row = dict(source)
        row_id = int(row.pop("id"))
        success = str(row.pop("success") or "pending_apply")
        ps_id = row.pop("port_security_id")
        ps_enabled = row.pop("port_security_enabled")
        ps_success = str(row.pop("port_security_success") or "")
        if row["mode"] == "hybrid":
            raise ValueError(
                "Cisco IOS push does not support hybrid port without an "
                f"explicit trunk profile: {row['if_name']}"
            )

        remove_port_security = bool(
            row["mode"] != "access"
            and ps_id is not None
            and not bool(ps_enabled)
            and ps_success in {"pending_apply", "pending_delete"}
        )
        row["disable_port_security"] = remove_port_security
        payload = {"interfaces": [row], "etherchannels": []}
        commands = render_commands("interfaces", payload)
        stp_row = stp_by_name.get(str(row["if_name"]))
        if stp_row is not None:
            commands.extend(
                render_commands("stp", {"global": [], "interfaces": [stp_row]})
            )

        success_rows = [{"kind": "interface", "id": row_id}]
        if remove_port_security:
            success_rows.append({"kind": "port_security", "id": int(ps_id)})
        task = task_factory(
            host,
            "interfaces",
            f"interface:{row['if_name']}",
            row["if_name"],
            payload,
            commands,
            {"success_rows": success_rows},
        )
        task["success"] = success
        tasks.append(task)
    return tasks


__all__ = ["build_interface_tasks"]
