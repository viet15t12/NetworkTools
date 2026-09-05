from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .common import boolean, failed, integer, ok, text, validate_ipv4_pair
from .entity_rules import require_active_vlan, require_immutable_identity
from .lifecycle import is_device_backed
from .navigation import normalize_switch_role
from .schema import ensure_switch_schema


def _require_sw3(conn: sqlite3.Connection, host: str) -> None:
    row = conn.execute("SELECT role FROM t01_devices WHERE host = ?;", (host,)).fetchone()
    if row is None or normalize_switch_role(row["role"]) != "sw3":
        raise ValueError("Layer 3 switch features require device role sw3")


def get_ip_routing(db: Any, host: str) -> dict[str, Any]:
    target = text(host)
    if not target:
        return {"ip_routing": 0, "updated_at": "", "sync_status": "synchronized"}
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        row = conn.execute(
            "SELECT ip_routing, updated_at, sync_status "
            "FROM t06_switch_l3_config WHERE host = ?;",
            (target,),
        ).fetchone()
    return dict(row) if row else {
        "ip_routing": 0,
        "updated_at": "",
        "sync_status": "synchronized",
    }


def save_ip_routing(db: Any, host: str, enabled: Any) -> dict[str, Any]:
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        with closing(db._connect()) as conn:
            with conn:
                _require_sw3(conn, target)
                conn.execute(
                    """
                    INSERT INTO t06_switch_l3_config(
                        host, ip_routing, updated_at, sync_status
                    )
                    VALUES (?, ?, datetime('now'), 'pending_apply')
                    ON CONFLICT(host) DO UPDATE SET
                        ip_routing = excluded.ip_routing,
                        updated_at = excluded.updated_at,
                        sync_status = 'pending_apply';
                    """,
                    (target, boolean(enabled)),
                )
        return ok("IP routing preference saved to the local workspace")
    except (sqlite3.Error, ValueError) as exc:
        return failed(str(exc))


def get_svis(db: Any, host: str) -> list[dict[str, Any]]:
    target = text(host)
    if not target:
        return []
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.vlan_id, v.vlan_name, s.ip_address,
                   s.subnet_mask, s.shutdown, s.sync_status
            FROM t06_svi_interface AS s
            JOIN t06_vlan_db AS v ON v.host = s.host AND v.vlan_id = s.vlan_id
            WHERE s.host = ? AND s.sync_status != 'pending_delete'
            ORDER BY s.vlan_id;
            """,
            (target,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_svi(db: Any, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        row_id = int(payload.get("id") or 0)
        vlan_id = integer(payload.get("vlan_id"), "VLAN ID", 1, 4094)
        ip_address, subnet_mask = validate_ipv4_pair(
            payload.get("ip_address"), payload.get("subnet_mask")
        )
        with closing(db._connect()) as conn:
            with conn:
                _require_sw3(conn, target)
                require_active_vlan(conn, target, vlan_id)
                duplicate_ip = conn.execute(
                    """
                    SELECT 1 FROM t06_svi_interface
                    WHERE host = ? AND ip_address = ? AND id != ? AND sync_status != 'pending_delete';
                    """,
                    (target, ip_address, row_id),
                ).fetchone()
                if ip_address and duplicate_ip is not None:
                    raise ValueError("The IPv4 address is already assigned to another SVI")
                if row_id > 0:
                    require_immutable_identity(
                        conn,
                        table="t06_svi_interface",
                        id_column="vlan_id",
                        row_id=row_id,
                        host=target,
                        current_value=vlan_id,
                        label="SVI",
                    )
                    cursor = conn.execute(
                        """
                        UPDATE t06_svi_interface
                        SET vlan_id = ?, ip_address = ?, subnet_mask = ?,
                            shutdown = ?, sync_status = 'pending_apply'
                        WHERE id = ? AND host = ?;
                        """,
                        (
                            vlan_id,
                            ip_address,
                            subnet_mask,
                            boolean(payload.get("shutdown")),
                            row_id,
                            target,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("The selected SVI no longer exists")
                    saved_id = row_id
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO t06_svi_interface(
                            host, vlan_id, ip_address, subnet_mask, shutdown, sync_status
                        ) VALUES (?, ?, ?, ?, ?, 'pending_apply');
                        """,
                        (
                            target,
                            vlan_id,
                            ip_address,
                            subnet_mask,
                            boolean(payload.get("shutdown")),
                        ),
                    )
                    saved_id = int(cursor.lastrowid)
        return ok("SVI saved to the local workspace", id=saved_id)
    except (sqlite3.Error, ValueError) as exc:
        return failed(str(exc))


def delete_svi(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Discard a local SVI draft or stage removal of a device-backed SVI."""
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        with closing(db._connect()) as conn:
            with conn:
                _require_sw3(conn, target)
                row = conn.execute(
                    "SELECT vlan_id, sync_status, device_present "
                    "FROM t06_svi_interface "
                    "WHERE id = ? AND host = ?;",
                    (int(row_id), target),
                ).fetchone()
                if row is None:
                    raise ValueError("The selected SVI no longer exists")
                if not is_device_backed(row, "sync_status"):
                    conn.execute(
                        "DELETE FROM t06_svi_interface WHERE id = ? AND host = ?;",
                        (int(row_id), target),
                    )
                    return ok(
                        f"SVI Vlan{row['vlan_id']} local draft deleted",
                        removed=True,
                    )
                conn.execute(
                    "UPDATE t06_svi_interface SET sync_status = 'pending_delete' "
                    "WHERE id = ? AND host = ?;",
                    (int(row_id), target),
                )
        return ok(
            f"SVI Vlan{row['vlan_id']} marked for removal; use Push to apply",
            removed=False,
        )
    except (sqlite3.Error, TypeError, ValueError) as exc:
        return failed(str(exc))
