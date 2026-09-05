from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .common import choice, failed, integer, ok, text
from .entity_rules import require_active_vlan, require_immutable_identity
from .schema import ensure_switch_schema


def get_stp_configs(db: Any, host: str) -> list[dict[str, Any]]:
    target = text(host)
    if not target:
        return []
    ensure_switch_schema(db)
    with closing(db._connect()) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.vlan_id, v.vlan_name, s.stp_mode, s.priority,
                   s.root_role, s.success
            FROM t06_stp_config AS s
            LEFT JOIN t06_vlan_db AS v
              ON v.host = s.host AND v.vlan_id = s.vlan_id
            WHERE s.host = ?
              AND COALESCE(s.success, 'pending_apply') <> 'pending_delete'
            ORDER BY s.vlan_id;
            """,
            (target,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_stp_config(db: Any, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Save one per-VLAN STP policy while keeping IOS global mode consistent."""
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        row_id = int(payload.get("id") or 0)
        vlan_id = integer(payload.get("vlan_id"), "VLAN ID", 1, 4094)
        stp_mode = choice(
            payload.get("stp_mode"),
            "STP mode",
            {"pvst", "rapid-pvst"},
            "rapid-pvst",
        )
        priority = integer(payload.get("priority", 32768), "STP priority", 0, 61440)
        if priority % 4096 != 0:
            raise ValueError("STP priority must be a multiple of 4096")
        root_role = choice(
            payload.get("root_role"),
            "Root role",
            {"primary", "secondary", "none"},
            "none",
        )

        with closing(db._connect()) as conn:
            with conn:
                require_active_vlan(conn, target, vlan_id)

                if row_id > 0:
                    require_immutable_identity(
                        conn,
                        table="t06_stp_config",
                        id_column="vlan_id",
                        row_id=row_id,
                        host=target,
                        current_value=vlan_id,
                        label="STP policy",
                    )

                duplicate = conn.execute(
                    """
                    SELECT 1 FROM t06_stp_config
                    WHERE host = ? AND vlan_id = ? AND id <> ?;
                    """,
                    (target, vlan_id, row_id),
                ).fetchone()
                if duplicate is not None:
                    raise ValueError(f"An STP policy already exists for VLAN {vlan_id}")

                # Cisco IOS exposes this as a global setting. Updating all saved
                # rows prevents desired-state validation from seeing mixed modes.
                conn.execute(
                    """
                    UPDATE t06_stp_config
                    SET stp_mode = ?, success = 'pending_apply'
                    WHERE host = ?;
                    """,
                    (stp_mode, target),
                )
                if row_id > 0:
                    cursor = conn.execute(
                        """
                        UPDATE t06_stp_config
                        SET vlan_id = ?, stp_mode = ?, priority = ?, root_role = ?,
                            success = 'pending_apply'
                        WHERE id = ? AND host = ?;
                        """,
                        (vlan_id, stp_mode, priority, root_role, row_id, target),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError("The selected STP policy no longer exists")
                    saved_id = row_id
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO t06_stp_config(
                            host, vlan_id, stp_mode, priority, root_role
                        ) VALUES (?, ?, ?, ?, ?);
                        """,
                        (target, vlan_id, stp_mode, priority, root_role),
                    )
                    saved_id = int(cursor.lastrowid)
        return ok("STP policy saved to the local workspace", id=saved_id)
    except (sqlite3.Error, ValueError, TypeError) as exc:
        return failed(str(exc))
