from __future__ import annotations

from contextlib import closing
from typing import Any


MODULES = ("vlan", "svi", "interfaces", "stp", "vtp", "security")


def _rows(conn: Any, sql: str, host: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, (host,)).fetchall()]


def collect_vlan_state(conn: Any, host: str) -> dict[str, Any]:
    return {
        "vlans": _rows(
            conn,
            """
            SELECT vlan_id, vlan_name, state
            FROM t06_vlan_db WHERE host = ? ORDER BY vlan_id;
            """,
            host,
        )
    }


def collect_svi_state(conn: Any, host: str) -> dict[str, Any]:
    routing = conn.execute(
        "SELECT ip_routing FROM t06_switch_l3_config WHERE host = ?;",
        (host,),
    ).fetchone()
    return {
        "ip_routing": bool(routing["ip_routing"]) if routing else False,
        "svis": _rows(
            conn,
            """
            SELECT vlan_id, ip_address, subnet_mask, shutdown
            FROM t06_svi_interface
            WHERE host = ? AND sync_status != 'pending_delete'
            ORDER BY vlan_id;
            """,
            host,
        ),
    }


def collect_interface_state(conn: Any, host: str) -> dict[str, Any]:
    interfaces = collect_switch_port_state(conn, host)["interfaces"]
    channels = collect_etherchannel_state(conn, host)["etherchannels"]
    return {"interfaces": interfaces, "etherchannels": channels}


def collect_switch_port_state(conn: Any, host: str) -> dict[str, Any]:
    interfaces = _rows(
        conn,
        """
        SELECT i.if_name, i.description, i.mode, i.admin_status, i.speed, i.duplex,
               a.access_vlan, a.voice_vlan,
               t.allowed_vlans, t.native_vlan, t.encapsulation, t.pruning_vlans
        FROM t06_interface_l2 AS i
        LEFT JOIN t06_iface_access AS a ON a.iface_id = i.id
        LEFT JOIN t06_iface_trunk AS t ON t.iface_id = i.id
        WHERE i.host = ?
        ORDER BY i.if_name COLLATE NOCASE;
        """,
        host,
    )
    unsupported = [row["if_name"] for row in interfaces if row["mode"] == "hybrid"]
    if unsupported:
        raise ValueError(
            "Cisco IOS push does not support hybrid ports without an explicit trunk profile: "
            + ", ".join(unsupported)
        )
    return {"interfaces": interfaces}


def collect_etherchannel_state(conn: Any, host: str) -> dict[str, Any]:
    channels = _rows(
        conn,
        """
        SELECT po_number, protocol, mode, member_ports, description
        FROM t06_etherchannel WHERE host = ? ORDER BY po_number;
        """,
        host,
    )
    valid_modes = {
        "lacp": {"active", "passive"},
        "pagp": {"desirable", "auto"},
        "static": {"on"},
    }
    invalid = [
        str(row["po_number"])
        for row in channels
        if row["mode"] not in valid_modes[row["protocol"]]
    ]
    if invalid:
        raise ValueError(
            "EtherChannel protocol/mode mismatch on Port-channel: " + ", ".join(invalid)
        )
    return {"etherchannels": channels}


def collect_stp_state(conn: Any, host: str) -> dict[str, Any]:
    global_rows = _rows(
        conn,
        """
        SELECT vlan_id, stp_mode, priority, root_role
        FROM t06_stp_config WHERE host = ? ORDER BY vlan_id;
        """,
        host,
    )
    modes = {row["stp_mode"] for row in global_rows}
    if len(modes) > 1:
        raise ValueError("A Cisco IOS switch cannot use multiple global STP modes")
    return {
        "global": global_rows,
        "interfaces": _rows(
            conn,
            """
            SELECT i.if_name, s.portfast, s.bpduguard, s.bpdufilter,
                   s.root_guard, s.loop_guard
            FROM t06_interface_l2 AS i
            JOIN t06_iface_stp AS s ON s.iface_id = i.id
            WHERE i.host = ? AND i.mode <> 'routed'
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            host,
        ),
    }


def collect_vtp_state(conn: Any, host: str) -> dict[str, Any]:
    rows = _rows(
        conn,
        """
        SELECT d.domain_name, d.version, d.password_type, d.password_value,
               s.pruning, m.database_type, m.mode, m.primary_server
        FROM t09_vtp_switches AS s
        JOIN t09_vtp_domains AS d ON d.vtp_domain_id = s.vtp_domain_id
        LEFT JOIN t09_vtp_database_modes AS m ON m.vtp_switch_id = s.vtp_switch_id
        WHERE s.host = ?
        ORDER BY m.database_type;
        """,
        host,
    )
    if any(row["password_type"] != "none" for row in rows):
        raise ValueError(
            "VTP authentication is stored encrypted and cannot be pushed until a decryptor is wired"
        )
    if any(row["database_type"] not in (None, "vlan") or row["primary_server"] for row in rows):
        raise ValueError("VTPv3 MST/primary-server activation requires an interactive workflow")
    return {"vtp": rows}


def collect_security_state(conn: Any, host: str) -> dict[str, Any]:
    return {
        "vlans": _rows(
            conn,
            """
            SELECT vlan_id, dhcp_snooping, dai_enabled
            FROM t06_security_l2 WHERE host = ? ORDER BY vlan_id;
            """,
            host,
        ),
        "trust_ports": [
            row["if_name"]
            for row in _rows(
                conn,
                """
                SELECT if_name FROM t06_dhcp_trust_ports
                WHERE host = ? ORDER BY if_name COLLATE NOCASE;
                """,
                host,
            )
        ],
        "ports": _rows(
            conn,
            """
            SELECT i.if_name,
                   COALESCE(ps.enabled, 0) AS enabled,
                   ps.max_mac, ps.violation, ps.sticky, ps.aging_type, ps.aging_time
            FROM t06_interface_l2 AS i
            LEFT JOIN t06_iface_port_security AS ps ON ps.iface_id = i.id
            WHERE i.host = ? AND i.mode = 'access'
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            host,
        ),
        "static_macs": _rows(
            conn,
            """
            SELECT i.if_name, m.mac_addr, m.vlan_id
            FROM t06_iface_mac_table AS m
            JOIN t06_interface_l2 AS i ON i.id = m.iface_id
            WHERE i.host = ? AND m.mac_type = 'static'
            ORDER BY m.vlan_id, m.mac_addr;
            """,
            host,
        ),
    }


def collect_port_security_state(conn: Any, host: str) -> dict[str, Any]:
    """Return only explicitly managed policies, including disabled pending rows."""
    return {
        "ports": _rows(
            conn,
            """
            SELECT i.if_name, ps.iface_id AS port_security_id,
                   ps.enabled, ps.max_mac, ps.violation, ps.sticky,
                   ps.aging_type, ps.aging_time, ps.sync_status, ps.success
            FROM t06_iface_port_security AS ps
            JOIN t06_interface_l2 AS i ON i.id = ps.iface_id
            WHERE i.host = ? AND i.mode = 'access'
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            host,
        )
    }


def collect_desired_state(db: Any, host: str, module_name: str) -> dict[str, Any]:
    collectors = {
        "vlan": collect_vlan_state,
        "svi": collect_svi_state,
        "interfaces": collect_interface_state,
        "stp": collect_stp_state,
        "vtp": collect_vtp_state,
        "security": collect_security_state,
    }
    if module_name not in collectors:
        raise ValueError(f"Unsupported Layer 2 module: {module_name}")
    with closing(db._connect()) as conn:
        return collectors[module_name](conn, host)
