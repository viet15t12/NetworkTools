"""Deletion workflows for switch policy rows that require matching IOS commands."""

from __future__ import annotations

import sqlite3
from typing import Any

from peewee import PeeweeException

from .common import failed, ok, text
from .peewee_context import switching_orm
from .schema import ensure_switch_schema


def _stage_host_row(
    db: Any,
    host: str,
    row_id: int,
    *,
    model_name: str,
    label: str,
) -> dict[str, Any]:
    """Mark a host-owned policy for device removal on the next Push.

    ``model_name`` is supplied only by the private wrappers below, so callers
    cannot inject a table name into a dynamically assembled SQL statement.
    """
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        entity_id = int(row_id)
        if entity_id <= 0:
            raise ValueError(f"A valid {label} is required")
        with switching_orm(db) as models:
            model = getattr(models, model_name)
            with models.database.atomic():
                affected = (
                    model.update(success="pending_delete")
                    .where((model.id == entity_id) & (model.host == target))
                    .execute()
                )
                if affected != 1:
                    raise ValueError(f"The selected {label} no longer exists")
        return ok(f"{label} marked for removal; use Push to apply", removed=False)
    except (PeeweeException, sqlite3.Error, TypeError, ValueError) as exc:
        return failed(str(exc))


def delete_stp_config(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Stage removal of one per-VLAN STP election policy."""
    return _stage_host_row(
        db, host, row_id, model_name="stp", label="STP policy"
    )


def delete_l2_vlan_security(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Stage removal of DHCP Snooping and DAI settings for one VLAN."""
    return _stage_host_row(
        db, host, row_id, model_name="l2_vlan", label="VLAN protection policy"
    )


def delete_l2_trust_port(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Stage removal of DHCP Snooping and DAI trust from one interface."""
    return _stage_host_row(
        db, host, row_id, model_name="trust_port", label="trusted uplink"
    )


def delete_static_mac(db: Any, host: str, row_id: int) -> dict[str, Any]:
    """Stage removal of a host-owned static MAC forwarding entry."""
    target = text(host)
    if not target:
        return failed("Host is required")
    try:
        ensure_switch_schema(db)
        entity_id = int(row_id)
        if entity_id <= 0:
            raise ValueError("A valid static MAC binding is required")
        with switching_orm(db) as models:
            with models.database.atomic():
                host_interfaces = models.interface.select(
                    models.interface.id
                ).where(models.interface.host == target)
                affected = (
                    models.static_mac.update(success="pending_delete")
                    .where(
                        (models.static_mac.id == entity_id)
                        & (models.static_mac.mac_type == "static")
                        & (models.static_mac.iface_id.in_(host_interfaces))
                    )
                    .execute()
                )
                if affected != 1:
                    raise ValueError("The selected static MAC binding no longer exists")
        return ok(
            "Static MAC binding marked for removal; use Push to apply",
            removed=False,
        )
    except (PeeweeException, sqlite3.Error, TypeError, ValueError) as exc:
        return failed(str(exc))


__all__ = [
    "delete_l2_trust_port",
    "delete_l2_vlan_security",
    "delete_static_mac",
    "delete_stp_config",
]
