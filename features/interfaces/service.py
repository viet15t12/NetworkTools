"""Router-interface use cases exposed to the QML facade."""

from __future__ import annotations

from typing import Any

from .common import db_connection, normalize_host
from .models import (
    CAPABILITIES,
    InterfaceType,
    canonical_interface_name,
    infer_interface_type,
)
from .repository import (
    get_router_interface_by_id,
    get_router_interface_by_name,
    save_router_interface,
)
from .validation import InterfaceValidationError, validate_payload, virtual_interface_name


class InterfaceService:
    def __init__(self, db: Any) -> None:
        self.db = db

    def capabilities(self, host: str) -> dict[str, Any]:
        target = normalize_host(host)
        with db_connection(self.db) as conn:
            row = conn.execute("SELECT role FROM t01_devices WHERE host = ?", (target,)).fetchone()
        role = str(row["role"] or "") if row else ""
        supported = [
            {
                "type": kind.value,
                "canCreate": capability.can_create,
                "canDelete": capability.can_delete,
                "canConfigureL1": capability.can_configure_l1,
            }
            for kind, capability in CAPABILITIES.items()
        ]
        return {"ok": bool(row), "host": target, "role": role, "types": supported}

    def save(self, payload_value: Any) -> dict[str, Any]:
        payload = self.db._as_dict(payload_value)
        host = normalize_host(payload.get("host"))
        if not host:
            return {"ok": False, "message": "Host is required"}
        candidate_name = canonical_interface_name(payload.get("interface_name"))
        named_interface = get_router_interface_by_name(self.db, host, candidate_name)
        requested_id = self.db._int_or_none(payload.get("iface_id"))
        source_interface = (
            get_router_interface_by_id(self.db, requested_id)
            if requested_id is not None and requested_id > 0
            else {}
        )
        if source_interface and str(source_interface.get("host") or "") != host:
            return {"ok": False, "message": "Interface does not belong to the selected host"}
        if source_interface and source_interface.get("interface_name") != candidate_name:
            if source_interface.get("sync_status") != "pending_apply":
                return {
                    "ok": False,
                    "message": "Only an unpushed virtual interface can be renumbered",
                }
            if infer_interface_type(source_interface.get("interface_name")) is not infer_interface_type(candidate_name):
                return {
                    "ok": False,
                    "message": "A virtual interface can only be renumbered within the same type",
                }
            if named_interface and named_interface.get("iface_id") != requested_id:
                return {"ok": False, "message": f"{candidate_name} already exists"}
        existing = bool(named_interface or source_interface)
        try:
            normalized = validate_payload(payload, existing=existing)
        except InterfaceValidationError as exc:
            return {"ok": False, "message": str(exc)}
        if not save_router_interface(self.db, normalized):
            return {"ok": False, "message": "Could not save the router interface"}
        row = get_router_interface_by_name(self.db, host, normalized["interface_name"])
        return {"ok": True, "message": "Router interface saved locally", "interface": row}

    def create_virtual(self, host: str, interface_type: str, payload_value: Any) -> dict[str, Any]:
        payload = self.db._as_dict(payload_value)
        try:
            name = virtual_interface_name(interface_type, payload)
        except InterfaceValidationError as exc:
            return {"ok": False, "message": str(exc)}
        if get_router_interface_by_name(self.db, host, name):
            return {"ok": False, "message": f"{name} already exists"}
        payload.update({"host": host, "interface_name": name})
        kind = InterfaceType(str(interface_type).strip().lower())
        payload["interface_kind"] = "Tunnel" if kind is InterfaceType.TUNNEL else "Subinterface" if kind is InterfaceType.SUBINTERFACE else "L3"
        if kind is InterfaceType.SUBINTERFACE:
            payload.setdefault("vlan_id", payload.get("number"))
            payload.setdefault("encapsulation", "dot1q")
        return self.save(payload)

    def build_virtual_name(self, interface_type: str, payload_value: Any) -> dict[str, Any]:
        """Validate creation identity without writing an incomplete draft row."""
        payload = self.db._as_dict(payload_value)
        try:
            name = virtual_interface_name(interface_type, payload)
        except InterfaceValidationError as exc:
            return {"ok": False, "message": str(exc), "interfaceName": ""}
        return {"ok": True, "message": "Virtual interface name is valid", "interfaceName": name}


__all__ = ["InterfaceService"]
