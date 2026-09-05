from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .common import choice, failed, integer, ok, text
from .entity_rules import require_immutable_identity
from .lifecycle import is_device_backed
from .schema import ensure_switch_schema
from .vtp_membership import require_vlan_configuration_owner


def get_vlans(db: Any, host: str) -> list[dict[str, Any]]:
    target = text(host)
    if not target:
        return []
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT v.id, v.vlan_id, v.vlan_name, v.state, v.success,
                   COUNT(i.id) AS access_port_count
            FROM t06_vlan_db AS v
            LEFT JOIN t06_iface_access AS a
              ON a.access_vlan = v.vlan_id OR a.voice_vlan = v.vlan_id
            LEFT JOIN t06_interface_l2 AS i ON i.id = a.iface_id AND i.host = v.host
            WHERE v.host = ?
              AND COALESCE(v.success, 'pending_apply') <> 'pending_delete'
              AND (
                  v.device_present = 1
                  OR COALESCE(v.success, 'pending_apply') <> 'synchronized'
              )
            GROUP BY v.id
            ORDER BY v.vlan_id;
            """,
            (target,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_vlan(db: Any, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        require_vlan_configuration_owner(db, target)
        row_id = int(payload.get("id") or 0)
        vlan_id = integer(payload.get("vlan_id"), "VLAN ID", 1, 4094)
        name = text(payload.get("vlan_name"))
        state = choice(payload.get("state"), "VLAN state", {"active", "suspend"}, "active")
        with closing(db._connect()) as conn:
            with conn:
                if row_id > 0:
                    require_immutable_identity(
                        conn,
                        table="t06_vlan_db",
                        id_column="vlan_id",
                        row_id=row_id,
                        host=target,
                        current_value=vlan_id,
                        label="VLAN",
                    )
                    cursor = conn.execute(
                        """
                        UPDATE t06_vlan_db
                        SET vlan_id = ?, vlan_name = ?, state = ?,
                            success = 'pending_apply'
                        WHERE id = ? AND host = ?;
                        """,
                        (vlan_id, name, state, row_id, target),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("The selected VLAN no longer exists")
                    saved_id = row_id
                else:
                    cursor = conn.execute(
                        "INSERT INTO t06_vlan_db(host, vlan_id, vlan_name, state) VALUES (?, ?, ?, ?);",
                        (target, vlan_id, name, state),
                    )
                    saved_id = int(cursor.lastrowid)
        return ok("VLAN saved to the local workspace", id=saved_id)
    except (sqlite3.Error, ValueError) as exc:
        return failed(str(exc))


def delete_vlan(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Discard a VLAN draft or stage removal of a synchronized VLAN."""
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        require_vlan_configuration_owner(db, target)
        vlan_row_id = int(row_id)
        if vlan_row_id <= 0:
            raise ValueError("A valid VLAN is required")

        with closing(db._connect()) as conn:
            with conn:
                row = conn.execute(
                    """
                    SELECT vlan_id, success, device_present
                    FROM t06_vlan_db
                    WHERE id = ? AND host = ?;
                    """,
                    (vlan_row_id, target),
                ).fetchone()
                if row is None:
                    raise ValueError("The selected VLAN no longer exists")

                vlan_id = int(row["vlan_id"])
                if vlan_id == 1:
                    raise ValueError("VLAN 1 is the default VLAN and cannot be deleted")
                access_ports = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM t06_interface_l2 AS i
                    JOIN t06_iface_access AS a ON a.iface_id = i.id
                    WHERE i.host = ?
                      AND COALESCE(i.success, 'pending_apply') <> 'pending_delete'
                      AND (a.access_vlan = ? OR a.voice_vlan = ?);
                    """,
                    (target, vlan_id, vlan_id),
                ).fetchone()[0]
                svi_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM t06_svi_interface
                    WHERE host = ? AND vlan_id = ?;
                    """,
                    (target, vlan_id),
                ).fetchone()[0]
                stp_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM t06_stp_config
                    WHERE host = ? AND vlan_id = ?;
                    """,
                    (target, vlan_id),
                ).fetchone()[0]
                security_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM t06_security_l2
                    WHERE host = ? AND vlan_id = ?;
                    """,
                    (target, vlan_id),
                ).fetchone()[0]
                static_mac_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM t06_iface_mac_table AS m
                    JOIN t06_interface_l2 AS i ON i.id = m.iface_id
                    WHERE i.host = ? AND m.vlan_id = ? AND m.mac_type = 'static'
                    ;
                    """,
                    (target, vlan_id),
                ).fetchone()[0]
                trunks = conn.execute(
                    """
                    SELECT t.native_vlan
                    FROM t06_iface_trunk AS t
                    JOIN t06_interface_l2 AS i ON i.id = t.iface_id
                    WHERE i.host = ?;
                    """,
                    (target,),
                ).fetchall()
                trunk_count = sum(
                    1
                    for trunk in trunks
                    if int(trunk["native_vlan"]) == vlan_id
                )
                if any(
                    (
                        access_ports,
                        svi_count,
                        stp_count,
                        security_count,
                        static_mac_count,
                        trunk_count,
                    )
                ):
                    dependencies: list[str] = []
                    if access_ports:
                        dependencies.append(f"{access_ports} access/voice port(s)")
                    if svi_count:
                        dependencies.append(f"{svi_count} SVI(s)")
                    if stp_count:
                        dependencies.append(f"{stp_count} STP policy/policies")
                    if security_count:
                        dependencies.append(
                            f"{security_count} Layer 2 security policy/policies"
                        )
                    if static_mac_count:
                        dependencies.append(
                            f"{static_mac_count} static MAC binding(s)"
                        )
                    if trunk_count:
                        dependencies.append(f"{trunk_count} trunk profile(s)")
                    raise ValueError(
                        f"VLAN {vlan_id} is still used by " + " and ".join(dependencies)
                    )

                if not is_device_backed(row):
                    conn.execute(
                        "DELETE FROM t06_vlan_db WHERE id = ? AND host = ?;",
                        (vlan_row_id, target),
                    )
                    return ok(f"VLAN {vlan_id} local draft deleted", removed=True)

                conn.execute(
                    """
                    UPDATE t06_vlan_db
                    SET success = 'pending_delete'
                    WHERE id = ? AND host = ?;
                    """,
                    (vlan_row_id, target),
                )
        return ok(
            f"VLAN {vlan_id} marked for removal; use Push to apply",
            removed=False,
        )
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return failed(str(exc))
