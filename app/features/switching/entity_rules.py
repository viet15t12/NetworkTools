"""Cross-repository integrity rules for switch configuration entities.

The repository modules keep ownership of their SQL writes.  This module only
contains checks shared by more than one repository, so validation does not
drift between VLAN, SVI, STP, security and EtherChannel workflows.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def require_immutable_identity(
    conn: sqlite3.Connection,
    *,
    table: str,
    id_column: str,
    row_id: int,
    host: str,
    current_value: Any,
    label: str,
) -> None:
    """Reject changes to a device identity that require deleting the old object.

    Device keys such as a VLAN number or interface name are not ordinary
    editable attributes.  Keeping them immutable prevents an update from
    creating the new object while silently leaving the previous object behind.
    """
    row = conn.execute(
        f"SELECT {id_column} FROM {table} WHERE id = ? AND host = ?;",
        (row_id, host),
    ).fetchone()
    if row is None:
        raise ValueError(f"The selected {label} no longer exists")
    if str(row[id_column]).casefold() != str(current_value).casefold():
        raise ValueError(
            f"{label} identity cannot be changed; delete it and create a new one"
        )


def require_active_vlan(
    conn: sqlite3.Connection, host: str, vlan_id: int, field: str = "VLAN"
) -> None:
    """Require a VLAN that is locally staged or present on the switch.

    Full device synchronization retains absent rows when another local policy
    still references them, but marks ``device_present = 0``. Treating such a
    synchronized tombstone as selectable would reconnect Security/STP/SVI to a
    VLAN which no longer exists on the device.
    """
    found = conn.execute(
        """
        SELECT 1 FROM t06_vlan_db
        WHERE host = ? AND vlan_id = ?
          AND COALESCE(success, 'pending_apply') <> 'pending_delete'
          AND (
              device_present = 1
              OR COALESCE(success, 'pending_apply') <> 'synchronized'
          );
        """,
        (host, vlan_id),
    ).fetchone()
    if found is None:
        raise ValueError(
            f"{field} {vlan_id} does not exist on the switch or is pending deletion"
        )


def require_etherchannel_members(
    conn: sqlite3.Connection, host: str, members: list[str]
) -> None:
    """Ensure every EtherChannel member is an inventoried physical L2 port."""
    rows = conn.execute(
        """
        SELECT if_name, mode FROM t06_interface_l2
        WHERE host = ?;
        """,
        (host,),
    ).fetchall()
    inventory = {str(row["if_name"]).casefold(): str(row["mode"]) for row in rows}
    missing = [member for member in members if member.casefold() not in inventory]
    if missing:
        raise ValueError(
            "EtherChannel member interface does not exist on this switch: "
            + ", ".join(missing)
        )
    invalid = [
        member
        for member in members
        if inventory.get(member.casefold()) in {"routed", "hybrid"}
    ]
    if invalid:
        raise ValueError(
            "EtherChannel members must be access or trunk interfaces: "
            + ", ".join(invalid)
        )


def reject_pending_vlan_references(
    conn: sqlite3.Connection, host: str, expression: str, field: str
) -> None:
    """Reject explicit trunk expressions containing a VLAN staged for deletion.

    ``all`` remains valid because it follows the switch's existing VLAN set and
    naturally stops including a VLAN after that VLAN is removed.
    """
    normalized = str(expression or "").strip().lower()
    if normalized in {"", "all", "none"}:
        return
    pending = {
        int(row["vlan_id"])
        for row in conn.execute(
            "SELECT vlan_id FROM t06_vlan_db "
            "WHERE host = ? AND success = 'pending_delete';",
            (host,),
        ).fetchall()
    }
    referenced: set[int] = set()
    for part in normalized.split(","):
        bounds = [int(value) for value in part.strip().split("-")]
        referenced.update(
            range(bounds[0], bounds[-1] + 1) if len(bounds) == 2 else bounds
        )
    conflicts = sorted(pending & referenced)
    if conflicts:
        raise ValueError(
            f"{field} references VLAN(s) pending deletion: "
            + ", ".join(str(value) for value in conflicts)
        )


__all__ = [
    "require_active_vlan",
    "require_etherchannel_members",
    "require_immutable_identity",
    "reject_pending_vlan_references",
]
