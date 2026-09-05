from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .common import (
    boolean,
    choice,
    failed,
    integer,
    ok,
    optional_vlan,
    text,
    validate_vlan_expression,
)
from .entity_rules import (
    reject_pending_vlan_references,
    require_active_vlan,
    require_immutable_identity,
)
from .navigation import normalize_switch_role
from .schema import ensure_switch_schema


def get_switch_interfaces(db: Any, host: str) -> list[dict[str, Any]]:
    target = text(host)
    if not target:
        return []
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.if_name, i.description, i.mode, i.admin_status,
                   i.oper_status, i.speed, i.duplex, i.updated_at,
                   a.access_vlan, a.voice_vlan,
                   t.allowed_vlans, t.native_vlan, t.encapsulation, t.pruning_vlans,
                   s.portfast, s.bpduguard, s.bpdufilter, s.root_guard, s.loop_guard,
                   ps.max_mac, ps.violation, ps.sticky, ps.aging_type, ps.aging_time,
                   COALESCE(ps.enabled, 0) AS port_security_enabled,
                   ps.sync_status AS port_security_sync_status,
                   i.success, ps.success AS port_security_success
            FROM t06_interface_l2 AS i
            LEFT JOIN t06_iface_access AS a ON a.iface_id = i.id
            LEFT JOIN t06_iface_trunk AS t ON t.iface_id = i.id
            LEFT JOIN t06_iface_stp AS s ON s.iface_id = i.id
            LEFT JOIN t06_iface_port_security AS ps ON ps.iface_id = i.id
            WHERE i.host = ?
            ORDER BY i.if_name COLLATE NOCASE;
            """,
            (target,),
        ).fetchall()
    return [dict(row) for row in rows]


def _require_vlan(conn: sqlite3.Connection, host: str, vlan_id: int, field: str) -> None:
    """Compatibility wrapper for the shared active-VLAN integrity rule."""
    require_active_vlan(conn, host, vlan_id, field)


def _save_mode_profile(
    conn: sqlite3.Connection,
    host: str,
    iface_id: int,
    mode: str,
    payload: dict[str, Any],
) -> None:
    if mode == "access":
        access_vlan = integer(payload.get("access_vlan", 1), "Access VLAN", 1, 4094)
        voice_vlan = optional_vlan(payload.get("voice_vlan"), "Voice VLAN")
        if voice_vlan == access_vlan:
            raise ValueError("Voice VLAN must differ from Access VLAN")
        _require_vlan(conn, host, access_vlan, "Access VLAN")
        if voice_vlan is not None:
            _require_vlan(conn, host, voice_vlan, "Voice VLAN")
        conn.execute("DELETE FROM t06_iface_trunk WHERE iface_id = ?;", (iface_id,))
        conn.execute(
            """
            INSERT INTO t06_iface_access(iface_id, access_vlan, voice_vlan)
            VALUES (?, ?, ?)
            ON CONFLICT(iface_id) DO UPDATE SET
                access_vlan = excluded.access_vlan,
                voice_vlan = excluded.voice_vlan;
            """,
            (iface_id, access_vlan, voice_vlan),
        )
        return

    if mode == "trunk":
        native_vlan = integer(payload.get("native_vlan", 1), "Native VLAN", 1, 4094)
        _require_vlan(conn, host, native_vlan, "Native VLAN")
        allowed = validate_vlan_expression(
            payload.get("allowed_vlans"), "Allowed VLANs", "all"
        )
        pruning = validate_vlan_expression(
            payload.get("pruning_vlans"), "Pruning VLANs", "none"
        )
        reject_pending_vlan_references(conn, host, allowed, "Allowed VLANs")
        reject_pending_vlan_references(conn, host, pruning, "Pruning VLANs")
        encapsulation = choice(
            payload.get("encapsulation"),
            "Encapsulation",
            {"dot1q", "isl"},
            "dot1q",
        )
        conn.execute("DELETE FROM t06_iface_access WHERE iface_id = ?;", (iface_id,))
        conn.execute(
            """
            INSERT INTO t06_iface_trunk(
                iface_id, allowed_vlans, native_vlan, encapsulation, pruning_vlans
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(iface_id) DO UPDATE SET
                allowed_vlans = excluded.allowed_vlans,
                native_vlan = excluded.native_vlan,
                encapsulation = excluded.encapsulation,
                pruning_vlans = excluded.pruning_vlans;
            """,
            (iface_id, allowed, native_vlan, encapsulation, pruning),
        )
        return

    conn.execute("DELETE FROM t06_iface_access WHERE iface_id = ?;", (iface_id,))
    conn.execute("DELETE FROM t06_iface_trunk WHERE iface_id = ?;", (iface_id,))


def _save_optional_profiles(
    conn: sqlite3.Connection,
    iface_id: int,
    mode: str,
    payload: dict[str, Any],
) -> None:
    if mode == "routed":
        conn.execute("DELETE FROM t06_iface_stp WHERE iface_id = ?;", (iface_id,))
        # Keep an existing policy until View/Push sends its explicit removal.
        # Deleting the row here would lose the information required to render
        # ``no switchport port-security`` during an access-to-routed change.
        conn.execute(
            """
            UPDATE t06_iface_port_security
            SET enabled = 0, sync_status = 'pending_apply', success = 'pending_apply'
            WHERE iface_id = ? AND enabled <> 0;
            """,
            (iface_id,),
        )
        return

    conn.execute(
        """
        INSERT INTO t06_iface_stp(
            iface_id, portfast, bpduguard, bpdufilter, root_guard, loop_guard
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(iface_id) DO UPDATE SET
            portfast = excluded.portfast,
            bpduguard = excluded.bpduguard,
            bpdufilter = excluded.bpdufilter,
            root_guard = excluded.root_guard,
            loop_guard = excluded.loop_guard;
        """,
        (
            iface_id,
            choice(payload.get("portfast"), "PortFast", {"enabled", "disabled"}, "disabled"),
            choice(payload.get("bpduguard"), "BPDU Guard", {"enabled", "disabled"}, "disabled"),
            choice(payload.get("bpdufilter"), "BPDU Filter", {"enabled", "disabled"}, "disabled"),
            choice(payload.get("root_guard"), "Root Guard", {"enabled", "disabled"}, "disabled"),
            choice(payload.get("loop_guard"), "Loop Guard", {"enabled", "disabled"}, "disabled"),
        ),
    )

    if boolean(payload.get("port_security_enabled")):
        if mode != "access":
            raise ValueError("Port Security can only be enabled on an access port")
        max_mac = integer(payload.get("max_mac", 1), "Maximum MAC", 1, 16384)
        aging_time = integer(payload.get("aging_time", 0), "Aging time", 0, 1_000_000)
        conn.execute(
            """
            INSERT INTO t06_iface_port_security(
                iface_id, enabled, max_mac, violation, sticky, aging_type,
                aging_time, sync_status, success
            ) VALUES (?, 1, ?, ?, ?, ?, ?, 'pending_apply', 'pending_apply')
            ON CONFLICT(iface_id) DO UPDATE SET
                enabled = 1,
                max_mac = excluded.max_mac,
                violation = excluded.violation,
                sticky = excluded.sticky,
                aging_type = excluded.aging_type,
                aging_time = excluded.aging_time,
                sync_status = CASE
                    WHEN t06_iface_port_security.enabled <> excluded.enabled
                      OR t06_iface_port_security.max_mac <> excluded.max_mac
                      OR t06_iface_port_security.violation <> excluded.violation
                      OR t06_iface_port_security.sticky <> excluded.sticky
                      OR t06_iface_port_security.aging_type <> excluded.aging_type
                      OR t06_iface_port_security.aging_time <> excluded.aging_time
                    THEN 'pending_apply'
                    ELSE t06_iface_port_security.sync_status
                END,
                success = CASE
                    WHEN t06_iface_port_security.enabled <> excluded.enabled
                      OR t06_iface_port_security.max_mac <> excluded.max_mac
                      OR t06_iface_port_security.violation <> excluded.violation
                      OR t06_iface_port_security.sticky <> excluded.sticky
                      OR t06_iface_port_security.aging_type <> excluded.aging_type
                      OR t06_iface_port_security.aging_time <> excluded.aging_time
                    THEN 'pending_apply'
                    ELSE t06_iface_port_security.success
                END;
            """,
            (
                iface_id,
                max_mac,
                choice(
                    payload.get("violation"),
                    "Violation",
                    {"shutdown", "restrict", "protect"},
                    "shutdown",
                ),
                boolean(payload.get("sticky")),
                choice(
                    payload.get("aging_type"),
                    "Aging type",
                    {"absolute", "inactivity"},
                    "absolute",
                ),
                aging_time,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE t06_iface_port_security
            SET enabled = 0, sync_status = 'pending_apply', success = 'pending_apply'
            WHERE iface_id = ? AND enabled <> 0;
            """,
            (iface_id,),
        )

def save_switch_interface(
    db: Any, host: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Save an interface and all related profiles in one transaction."""
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        row_id = int(payload.get("id") or 0)
        if_name = text(payload.get("if_name"))
        if not if_name:
            raise ValueError("Interface name is required")
        mode = choice(
            payload.get("mode"),
            "Mode",
            {"access", "trunk", "hybrid", "routed"},
            "access",
        )
        values = (
            if_name,
            text(payload.get("description")),
            mode,
            choice(payload.get("admin_status"), "Admin status", {"up", "down"}, "up"),
            choice(
                payload.get("oper_status"),
                "Oper status",
                {"up", "down", "err-disabled", "unknown"},
                "unknown",
            ),
            choice(
                payload.get("speed"),
                "Speed",
                {"auto", "10", "100", "1000", "10000"},
                "auto",
            ),
            choice(payload.get("duplex"), "Duplex", {"auto", "full", "half"}, "auto"),
        )
        with closing(db._connect()) as conn:
            with conn:
                if mode == "routed":
                    device = conn.execute(
                        "SELECT role FROM t01_devices WHERE host = ?;", (target,)
                    ).fetchone()
                    if device is None or normalize_switch_role(device["role"]) != "sw3":
                        raise ValueError("Routed ports require device role sw3")
                if row_id > 0:
                    require_immutable_identity(
                        conn,
                        table="t06_interface_l2",
                        id_column="if_name",
                        row_id=row_id,
                        host=target,
                        current_value=if_name,
                        label="Interface",
                    )
                    cursor = conn.execute(
                        """
                        UPDATE t06_interface_l2
                        SET if_name = ?, description = ?, mode = ?, admin_status = ?,
                            oper_status = ?, speed = ?, duplex = ?,
                            updated_at = datetime('now'), success = 'pending_apply'
                        WHERE id = ? AND host = ?;
                        """,
                        (*values, row_id, target),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("The selected interface no longer exists")
                    saved_id = row_id
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO t06_interface_l2(
                            host, if_name, description, mode, admin_status,
                            oper_status, speed, duplex
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (target, *values),
                    )
                    saved_id = int(cursor.lastrowid)
                _save_mode_profile(conn, target, saved_id, mode, payload)
                _save_optional_profiles(conn, saved_id, mode, payload)
        return ok("Interface saved to the local workspace", id=saved_id)
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return failed(str(exc))
