from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .peewee_context import switching_orm


@dataclass(frozen=True)
class _SuccessTarget:
    """Whitelist one task kind and its model/status fields."""

    model: str
    identity: str
    status: str
    presence: str | None = None


_SUCCESS_TARGETS = {
    "vlan": _SuccessTarget("vlan", "id", "success", "device_present"),
    "svi": _SuccessTarget("svi", "id", "sync_status", "device_present"),
    "switch_l3": _SuccessTarget("switch_l3", "host", "sync_status"),
    "interface": _SuccessTarget("interface", "id", "success"),
    "etherchannel": _SuccessTarget(
        "etherchannel", "id", "success", "device_present"
    ),
    "stp": _SuccessTarget("stp", "id", "success"),
    "l2_vlan": _SuccessTarget("l2_vlan", "id", "success"),
    "trust_port": _SuccessTarget("trust_port", "id", "success"),
    "static_mac": _SuccessTarget("static_mac", "id", "success"),
    "port_security": _SuccessTarget("port_security", "iface_id", "success"),
    "vtp": _SuccessTarget("vtp", "vtp_switch_id", "success"),
}


def mark_task_success(db: Any, tracking: dict[str, Any]) -> None:
    """Atomically acknowledge only the rows represented by a successful task.

    The explicit target map prevents callers from supplying arbitrary table or
    column names.  Peewee also combines related lifecycle fields into one
    update, reducing the number of SQLite statements per successful task.
    """
    rows = tracking.get("success_rows") or []
    if not rows:
        raise ValueError("A successful switching task must identify its business row")
    with switching_orm(db) as models:
        with models.database.atomic():
            for row in rows:
                kind = str(row.get("kind") or "")
                target = _SUCCESS_TARGETS.get(kind)
                if target is None:
                    raise ValueError(f"Unsupported switching success target: {kind}")
                model = getattr(models, target.model)
                identity_field = getattr(model, target.identity)
                row_id = (
                    str(row["id"])
                    if target.identity == "host"
                    else int(row["id"])
                )
                if row.get("action") == "delete":
                    affected = model.delete().where(identity_field == row_id).execute()
                else:
                    values = {getattr(model, target.status): "synchronized"}
                    if target.presence:
                        values[getattr(model, target.presence)] = 1
                    if kind in {"port_security", "vtp"}:
                        values[model.sync_status] = "synchronized"
                    if kind == "etherchannel":
                        values[model.cleanup_member_ports] = ""
                    affected = (
                        model.update(values)
                        .where(identity_field == row_id)
                        .execute()
                    )
                if affected != 1:
                    raise ValueError(
                        f"Switching success row no longer exists: {kind}:{row_id}"
                    )


__all__ = ["mark_task_success"]
