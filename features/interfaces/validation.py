"""Backend validation and deterministic naming for router interfaces."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from .models import InterfaceType, canonical_interface_name, infer_interface_type


class InterfaceValidationError(ValueError):
    pass


def virtual_interface_name(interface_type: Any, payload: dict[str, Any]) -> str:
    try:
        kind = InterfaceType(str(interface_type or "").strip().lower())
    except ValueError as exc:
        raise InterfaceValidationError("Unsupported virtual interface type") from exc
    if kind is InterfaceType.PHYSICAL:
        raise InterfaceValidationError("Physical interfaces cannot be created manually")
    if kind in {InterfaceType.LOOPBACK, InterfaceType.TUNNEL}:
        number = _integer(payload.get("number"), "Interface number", 0, 2147483647)
        return f"{'Loopback' if kind is InterfaceType.LOOPBACK else 'Tunnel'}{number}"
    parent = canonical_interface_name(payload.get("parent_interface"))
    if infer_interface_type(parent) is not InterfaceType.PHYSICAL:
        raise InterfaceValidationError("Subinterface parent must be a physical interface")
    number = _integer(payload.get("number"), "Subinterface number", 1, 4294967295)
    return f"{parent}.{number}"


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise InterfaceValidationError(f"{label} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise InterfaceValidationError(f"{label} must be between {minimum} and {maximum}")
    return result


def normalize_ipv4(address: Any, mask: Any) -> tuple[str | None, str | None]:
    ip_text = str(address or "").strip()
    mask_text = str(mask or "").strip()
    if not ip_text and not mask_text:
        return None, None
    if not ip_text or not mask_text:
        raise InterfaceValidationError("IPv4 address and subnet mask must be provided together")
    try:
        interface = ipaddress.IPv4Interface(f"{ip_text}/{mask_text.lstrip('/')}")
    except ValueError as exc:
        raise InterfaceValidationError(f"Invalid IPv4 address or subnet mask: {exc}") from exc
    return str(interface.ip), str(interface.netmask)


def validate_payload(payload: dict[str, Any], *, existing: bool = False) -> dict[str, Any]:
    normalized = dict(payload)
    name = canonical_interface_name(normalized.get("interface_name"))
    if not name or not re.fullmatch(r"[A-Za-z][A-Za-z-]*\d[\d/]*(?:\.\d+)?", name):
        raise InterfaceValidationError("Interface name is invalid")
    normalized["interface_name"] = name
    address, mask = normalize_ipv4(
        normalized.get("ip_address"), normalized.get("subnet_mask")
    )
    normalized["ip_address"] = address
    normalized["subnet_mask"] = mask

    secondary_ip = normalized.get("secondary_ip")
    secondary_mask = normalized.get("secondary_mask")
    if secondary_ip or secondary_mask:
        secondary_ip, secondary_mask = normalize_ipv4(secondary_ip, secondary_mask)
    normalized["secondary_ip"] = secondary_ip
    normalized["secondary_mask"] = secondary_mask

    interface_type = infer_interface_type(name, normalized.get("interface_kind"))
    normalized["interface_type"] = interface_type.value
    requested_kind = str(normalized.get("interface_kind") or "L3").strip()
    allowed_kinds = {
        InterfaceType.PHYSICAL: {"L3", "WAN"},
        InterfaceType.LOOPBACK: {"L3"},
        InterfaceType.TUNNEL: {"Tunnel"},
        InterfaceType.SUBINTERFACE: {"Subinterface"},
    }
    if requested_kind not in allowed_kinds[interface_type]:
        raise InterfaceValidationError(
            f"{interface_type.value} interface does not support the {requested_kind} profile"
        )
    if interface_type is InterfaceType.TUNNEL:
        normalized["interface_kind"] = "Tunnel"
    elif interface_type is InterfaceType.SUBINTERFACE:
        normalized["interface_kind"] = "Subinterface"
        parent = canonical_interface_name(
            normalized.get("parent_interface") or name.rsplit(".", 1)[0]
        )
        expected_name = virtual_interface_name(
            InterfaceType.SUBINTERFACE,
            {"parent_interface": parent, "number": name.rsplit(".", 1)[1]},
        )
        if expected_name != name:
            raise InterfaceValidationError("Subinterface name does not match its parent")
        normalized["parent_interface"] = parent
        normalized["vlan_id"] = _integer(
            normalized.get("vlan_id") or name.rsplit(".", 1)[1],
            "VLAN ID",
            1,
            4094,
        )
    if interface_type is InterfaceType.TUNNEL:
        source = str(normalized.get("tunnel_src") or "").strip()
        destination = str(normalized.get("tunnel_dst") or "").strip()
        if not source or not destination:
            raise InterfaceValidationError("Tunnel source and destination are required")
        try:
            ipaddress.IPv4Address(destination)
        except ValueError as exc:
            raise InterfaceValidationError("Tunnel destination must be a valid IPv4 address") from exc
        normalized_source = canonical_interface_name(source)
        try:
            ipaddress.IPv4Address(normalized_source)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z][A-Za-z-]*\d[\d/]*(?:\.\d+)?", normalized_source):
                raise InterfaceValidationError(
                    "Tunnel source must be a valid IPv4 address or interface name"
                )
        normalized["tunnel_src"] = normalized_source
        normalized["tunnel_dst"] = destination
    if not existing and interface_type is InterfaceType.PHYSICAL:
        raise InterfaceValidationError("Physical interfaces must come from device discovery/profile")
    return normalized
