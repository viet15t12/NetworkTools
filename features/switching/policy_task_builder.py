"""Build View/Push tasks for STP and Layer 2 security policies."""

from __future__ import annotations

from contextlib import closing
from typing import Any, Callable

from .commands import render_commands


TaskFactory = Callable[..., dict[str, Any]]


def build_stp_tasks(
    db: Any, host: str, task_factory: TaskFactory
) -> list[dict[str, Any]]:
    """Build pending per-VLAN STP setup/removal tasks."""
    with closing(db._connect()) as conn:
        modes = {
            str(row["stp_mode"])
            for row in conn.execute(
                "SELECT DISTINCT stp_mode FROM t06_stp_config "
                "WHERE host = ? AND success <> 'pending_delete';",
                (host,),
            ).fetchall()
        }
        rows = conn.execute(
            """
            SELECT id, vlan_id, stp_mode, priority, root_role, success
            FROM t06_stp_config
            WHERE host = ? AND (
                success IN ('pending_apply','pending_delete') OR success IS NULL
            )
            ORDER BY vlan_id;
            """,
            (host,),
        ).fetchall()
    if len(modes) > 1:
        raise ValueError("A Cisco IOS switch cannot use multiple global STP modes")

    tasks: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        row_id = int(row.pop("id"))
        success = str(row.pop("success") or "pending_apply")
        row["action"] = "remove" if success == "pending_delete" else "setup"
        payload = {"global": [row], "interfaces": []}
        task = task_factory(
            host,
            "stp",
            f"vlan:{row['vlan_id']}",
            f"STP VLAN {row['vlan_id']}",
            payload,
            render_commands("stp", payload),
            {"success_rows": [{
                "kind": "stp",
                "id": row_id,
                "action": "delete" if success == "pending_delete" else "sync",
            }]},
        )
        task["success"] = success
        tasks.append(task)
    return tasks


def build_security_tasks(
    db: Any, host: str, module: str, task_factory: TaskFactory
) -> list[dict[str, Any]]:
    """Build Port Security or VLAN/trust/static-MAC tasks for one tab."""
    with closing(db._connect()) as conn:
        if module == "port_security":
            port_rows = conn.execute(
                """
                SELECT i.if_name, ps.iface_id AS id, ps.enabled, ps.max_mac,
                       ps.violation, ps.sticky, ps.aging_type, ps.aging_time,
                       ps.success
                FROM t06_iface_port_security AS ps
                JOIN t06_interface_l2 AS i ON i.id = ps.iface_id
                WHERE i.host = ? AND i.mode = 'access' AND (
                    ps.success IN ('pending_apply','pending_delete')
                    OR ps.success IS NULL
                )
                ORDER BY i.if_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
            vlan_rows = trust_rows = static_rows = []
        else:
            port_rows = []
            vlan_rows = conn.execute(
                """
                SELECT id, vlan_id, dhcp_snooping, dai_enabled, success
                FROM t06_security_l2
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                )
                ORDER BY vlan_id;
                """,
                (host,),
            ).fetchall()
            trust_rows = conn.execute(
                """
                SELECT id, if_name, success FROM t06_dhcp_trust_ports
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                )
                ORDER BY if_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
            static_rows = conn.execute(
                """
                SELECT m.id, m.mac_addr, m.vlan_id, i.if_name, m.success
                FROM t06_iface_mac_table AS m
                JOIN t06_interface_l2 AS i ON i.id = m.iface_id
                WHERE i.host = ? AND m.mac_type = 'static' AND (
                    m.success IN ('pending_apply','pending_delete') OR m.success IS NULL
                )
                ORDER BY m.vlan_id, m.mac_addr;
                """,
                (host,),
            ).fetchall()

    if module == "port_security":
        return _port_security_tasks(host, port_rows, task_factory)
    return _l2_security_tasks(
        host, module, vlan_rows, trust_rows, static_rows, task_factory
    )


def _port_security_tasks(
    host: str, rows: list[Any], task_factory: TaskFactory
) -> list[dict[str, Any]]:
    """Build managed Port Security enable/disable tasks."""
    tasks: list[dict[str, Any]] = []
    for source in rows:
        config = dict(source)
        row_id = int(config.pop("id"))
        success = str(config.pop("success") or "pending_apply")
        payload = {
            "vlans": [],
            "trust_ports": [],
            "ports": [config],
            "static_macs": [],
        }
        task = task_factory(
            host,
            "port_security",
            f"interface:{config['if_name']}",
            f"Port Security {config['if_name']}",
            payload,
            render_commands("security", payload),
            {"success_rows": [{"kind": "port_security", "id": row_id}]},
        )
        task["success"] = success
        tasks.append(task)
    return tasks


def _l2_security_tasks(
    host: str,
    module: str,
    vlan_rows: list[Any],
    trust_rows: list[Any],
    static_rows: list[Any],
    task_factory: TaskFactory,
) -> list[dict[str, Any]]:
    """Build VLAN protection, trusted-uplink and static-MAC tasks."""
    tasks: list[dict[str, Any]] = []
    for source in vlan_rows:
        row = dict(source)
        row_id = int(row.pop("id"))
        success = str(row.pop("success") or "pending_apply")
        if success == "pending_delete":
            row["dhcp_snooping"] = 0
            row["dai_enabled"] = 0
        payload = {"vlans": [row], "trust_ports": [], "ports": [], "static_macs": []}
        tasks.append(_policy_task(
            task_factory, host, module, f"vlan:{row['vlan_id']}",
            f"L2 Security VLAN {row['vlan_id']}", payload, "l2_vlan", row_id, success,
        ))

    for source in trust_rows:
        row = dict(source)
        row_id = int(row.pop("id"))
        success = str(row.pop("success") or "pending_apply")
        if_name = str(row["if_name"])
        entry: str | dict[str, str] = if_name
        if success == "pending_delete":
            entry = {"if_name": if_name, "action": "remove"}
        payload = {"vlans": [], "trust_ports": [entry], "ports": [], "static_macs": []}
        tasks.append(_policy_task(
            task_factory, host, module, f"trust:{if_name}",
            f"Trusted uplink {if_name}", payload, "trust_port", row_id, success,
        ))

    for source in static_rows:
        row = dict(source)
        row_id = int(row.pop("id"))
        success = str(row.pop("success") or "pending_apply")
        row["action"] = "remove" if success == "pending_delete" else "setup"
        payload = {"vlans": [], "trust_ports": [], "ports": [], "static_macs": [row]}
        key = f"static:{row['mac_addr']}:{row['vlan_id']}:{row['if_name']}"
        tasks.append(_policy_task(
            task_factory, host, module, key, f"Static MAC {row['mac_addr']}",
            payload, "static_mac", row_id, success,
        ))
    return tasks


def _policy_task(
    task_factory: TaskFactory,
    host: str,
    module: str,
    key: str,
    label: str,
    payload: dict[str, Any],
    kind: str,
    row_id: int,
    success: str,
) -> dict[str, Any]:
    """Create one security task with consistent lifecycle tracking metadata."""
    task = task_factory(
        host,
        module,
        key,
        label,
        payload,
        render_commands("security", payload),
        {"success_rows": [{
            "kind": kind,
            "id": row_id,
            "action": "delete" if success == "pending_delete" else "sync",
        }]},
    )
    task["success"] = success
    return task


__all__ = ["build_security_tasks", "build_stp_tasks"]
