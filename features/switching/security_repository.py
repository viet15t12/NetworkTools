"""Persistence rules shared by the switch Layer 2 Security surfaces.

The page deliberately reads VLANs and interfaces from the canonical switching
inventory instead of maintaining security-specific copies. This keeps VLAN
Protection, Trusted Uplinks, Static MAC, and Port Security consistent.
"""

from __future__ import annotations

import re
from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .common import boolean, failed, integer, ok, text
from .entity_rules import require_active_vlan
from .schema import ensure_switch_schema


def _canonical_mac(value: Any) -> str:
    compact = re.sub(r"[^0-9A-Fa-f]", "", text(value))
    if len(compact) != 12:
        raise ValueError("MAC address must contain exactly 12 hexadecimal digits")
    return ".".join(compact[index : index + 4] for index in range(0, 12, 4)).lower()


def get_l2_security(db: Any, host: str) -> dict[str, Any]:
    """Return one coherent security workspace snapshot for ``host``.

    Only usable, non-deleted Layer 2 interfaces are offered to Trusted Uplinks
    and Static MAC. Operational fields are included so the UI can explain why
    a port is a sensible uplink without issuing another network command.
    """
    target = text(host)
    if not target:
        return {"vlans": [], "trust_ports": [], "static_macs": [], "interfaces": []}
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        vlans = conn.execute(
            """
            SELECT COALESCE(s.id, 0) AS id, v.vlan_id, v.vlan_name,
                   COALESCE(s.dhcp_snooping, 0) AS dhcp_snooping,
                   COALESCE(s.dai_enabled, 0) AS dai_enabled,
                   COALESCE(s.success, 'skipped') AS success
            FROM t06_vlan_db AS v
            LEFT JOIN t06_security_l2 AS s
              ON s.host = v.host AND s.vlan_id = v.vlan_id
             AND COALESCE(s.success, 'pending_apply') <> 'pending_delete'
            WHERE v.host = ?
              AND COALESCE(v.success, 'pending_apply') <> 'pending_delete'
              AND (
                  v.device_present = 1
                  OR COALESCE(v.success, 'pending_apply') <> 'synchronized'
              )
            ORDER BY v.vlan_id;
            """,
            (target,),
        ).fetchall()
        trust_ports = conn.execute(
            """
            SELECT id, if_name, success FROM t06_dhcp_trust_ports
            WHERE host = ?
              AND COALESCE(success, 'pending_apply') <> 'pending_delete'
            ORDER BY if_name COLLATE NOCASE;
            """,
            (target,),
        ).fetchall()
        static_macs = conn.execute(
            """
            SELECT m.id, m.mac_addr, m.vlan_id, i.if_name, m.success
            FROM t06_iface_mac_table AS m
            JOIN t06_interface_l2 AS i ON i.id = m.iface_id
            WHERE i.host = ? AND m.mac_type = 'static'
              AND COALESCE(m.success, 'pending_apply') <> 'pending_delete'
            ORDER BY m.vlan_id, m.mac_addr;
            """,
            (target,),
        ).fetchall()
        interfaces = conn.execute(
            """
            SELECT id, if_name, description, mode, admin_status, oper_status,
                   success
            FROM t06_interface_l2
            WHERE host = ?
              AND mode <> 'routed'
              AND COALESCE(success, 'pending_apply') <> 'pending_delete'
            ORDER BY
                CASE mode WHEN 'trunk' THEN 0 WHEN 'hybrid' THEN 1 ELSE 2 END,
                if_name COLLATE NOCASE;
            """,
            (target,),
        ).fetchall()
    return {
        "vlans": [dict(row) for row in vlans],
        "trust_ports": [dict(row) for row in trust_ports],
        "static_macs": [dict(row) for row in static_macs],
        "interfaces": [dict(row) for row in interfaces],
    }


def save_l2_vlan_security(db: Any, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Stage DHCP Snooping/DAI policy for one active VLAN.

    This application does not model ARP ACLs, so DAI must use the DHCP Snooping
    binding database. Enforcing that dependency avoids generating a policy
    which looks protected in the UI but cannot validate dynamic bindings.
    """
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        vlan_id = integer(payload.get("vlan_id"), "VLAN ID", 1, 4094)
        snooping = boolean(payload.get("dhcp_snooping"))
        dai = boolean(payload.get("dai_enabled"))
        if dai and not snooping:
            raise ValueError(
                "Enable DHCP Snooping before Dynamic ARP Inspection; "
                "ARP ACL-based DAI is not managed by this workflow"
            )
        with closing(db._connect()) as conn:
            with conn:
                require_active_vlan(conn, target, vlan_id)
                conn.execute(
                    """
                    INSERT INTO t06_security_l2(
                        host, vlan_id, dhcp_snooping, dai_enabled
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(host, vlan_id) DO UPDATE SET
                        dhcp_snooping = excluded.dhcp_snooping,
                        dai_enabled = excluded.dai_enabled,
                        success = 'pending_apply';
                    """,
                    (target, vlan_id, snooping, dai),
                )
                saved = conn.execute(
                    "SELECT id FROM t06_security_l2 WHERE host = ? AND vlan_id = ?;",
                    (target, vlan_id),
                ).fetchone()
                if saved is None:
                    raise ValueError("VLAN protection policy could not be saved")
                saved_id = int(saved["id"])
        return ok("VLAN protection policy saved", id=saved_id)
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return failed(str(exc))


def add_l2_trust_port(db: Any, host: str, if_name: Any) -> dict[str, Any]:
    """Stage one existing Layer 2 port as the trusted server/uplink path."""
    target = text(host)
    interface = text(if_name)
    if not target or not interface:
        return failed("Host and interface are required")
    try:
        ensure_switch_schema(db)
        with closing(db._connect()) as conn:
            with conn:
                found = conn.execute(
                    """
                    SELECT 1 FROM t06_interface_l2
                    WHERE host = ? AND if_name = ? AND mode <> 'routed'
                      AND COALESCE(success, 'pending_apply') <> 'pending_delete';
                    """,
                    (target, interface),
                ).fetchone()
                if found is None:
                    raise ValueError("Trust port must be an existing Layer 2 interface")
                cursor = conn.execute(
                    """
                    INSERT INTO t06_dhcp_trust_ports(host, if_name, success)
                    VALUES (?, ?, 'pending_apply');
                    """,
                    (target, interface),
                )
        return ok("Trusted uplink added", id=int(cursor.lastrowid))
    except (sqlite3.Error, ValueError) as exc:
        return failed(str(exc))


def save_static_mac(db: Any, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        row_id = int(payload.get("id") or 0)
        interface = text(payload.get("if_name"))
        vlan_id = integer(payload.get("vlan_id"), "VLAN ID", 1, 4094)
        mac_addr = _canonical_mac(payload.get("mac_addr"))
        with closing(db._connect()) as conn:
            with conn:
                require_active_vlan(conn, target, vlan_id)
                row = conn.execute(
                    """
                    SELECT i.id FROM t06_interface_l2 AS i
                    JOIN t06_vlan_db AS v ON v.host = i.host AND v.vlan_id = ?
                    WHERE i.host = ? AND i.if_name = ? AND i.mode <> 'routed';
                    """,
                    (vlan_id, target, interface),
                ).fetchone()
                if row is None:
                    raise ValueError("Static MAC requires an existing VLAN and Layer 2 interface")
                iface_id = int(row["id"])
                if row_id > 0:
                    existing = conn.execute(
                        """
                        SELECT m.mac_addr, m.vlan_id, i.if_name, m.success
                        FROM t06_iface_mac_table AS m
                        JOIN t06_interface_l2 AS i ON i.id = m.iface_id
                        WHERE m.id = ? AND m.mac_type = 'static' AND i.host = ?;
                        """,
                        (row_id, target),
                    ).fetchone()
                    if existing is None:
                        raise ValueError(
                            "The selected static MAC binding no longer exists"
                        )
                    identity_changed = (
                        str(existing["mac_addr"]).casefold() != mac_addr.casefold()
                        or int(existing["vlan_id"]) != vlan_id
                        or str(existing["if_name"]).casefold() != interface.casefold()
                    )
                    if identity_changed and str(existing["success"]) != "pending_apply":
                        raise ValueError(
                            "A synchronized static MAC identity cannot be changed; "
                            "delete it and create a new binding"
                        )
                    cursor = conn.execute(
                        """
                        UPDATE t06_iface_mac_table
                        SET iface_id = ?, mac_addr = ?, vlan_id = ?, mac_type = 'static',
                            success = 'pending_apply'
                        WHERE id = ? AND mac_type = 'static'
                          AND iface_id IN (
                              SELECT id FROM t06_interface_l2 WHERE host = ?
                          );
                        """,
                        (iface_id, mac_addr, vlan_id, row_id, target),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("The selected static MAC binding no longer exists")
                    saved_id = row_id
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO t06_iface_mac_table(
                            iface_id, mac_addr, vlan_id, mac_type
                        ) VALUES (?, ?, ?, 'static');
                        """,
                        (iface_id, mac_addr, vlan_id),
                    )
                    saved_id = int(cursor.lastrowid)
        return ok("Static MAC binding saved", id=saved_id)
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return failed(str(exc))
