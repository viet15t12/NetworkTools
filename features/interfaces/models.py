"""Domain types and QML-facing metadata for router interfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class InterfaceType(StrEnum):
    PHYSICAL = "physical"
    LOOPBACK = "loopback"
    TUNNEL = "tunnel"
    SUBINTERFACE = "subinterface"


_CANONICAL_PREFIXES = {
    "gi": "GigabitEthernet",
    "gig": "GigabitEthernet",
    "gigabitethernet": "GigabitEthernet",
    "fa": "FastEthernet",
    "fastethernet": "FastEthernet",
    "te": "TenGigabitEthernet",
    "tengigabitethernet": "TenGigabitEthernet",
    "eth": "Ethernet",
    "ethernet": "Ethernet",
    "se": "Serial",
    "serial": "Serial",
    "lo": "Loopback",
    "loopback": "Loopback",
    "tu": "Tunnel",
    "tunnel": "Tunnel",
}


def canonical_interface_name(value: Any) -> str:
    name = str(value or "").strip().replace(" ", "")
    match = re.fullmatch(r"([A-Za-z-]+)(\d[\d/]*(?:\.\d+)?)", name)
    if not match:
        return name
    prefix = _CANONICAL_PREFIXES.get(match.group(1).lower(), match.group(1))
    return prefix + match.group(2)


def short_interface_name(value: Any) -> str:
    name = canonical_interface_name(value)
    for prefix, short in (
        ("TenGigabitEthernet", "Te"),
        ("GigabitEthernet", "Gi"),
        ("FastEthernet", "Fa"),
        ("Ethernet", "Eth"),
        ("Serial", "Se"),
        ("Loopback", "Lo"),
        ("Tunnel", "Tu"),
    ):
        if name.startswith(prefix):
            return short + name[len(prefix) :]
    return name


def infer_interface_type(name: Any, profile_kind: Any = "") -> InterfaceType:
    canonical = canonical_interface_name(name)
    if "." in canonical:
        return InterfaceType.SUBINTERFACE
    if canonical.startswith("Loopback"):
        return InterfaceType.LOOPBACK
    if canonical.startswith("Tunnel"):
        return InterfaceType.TUNNEL
    return InterfaceType.PHYSICAL


@dataclass(frozen=True)
class InterfaceCapabilities:
    can_create: bool
    can_delete: bool
    can_configure_l1: bool


CAPABILITIES = {
    InterfaceType.PHYSICAL: InterfaceCapabilities(False, False, True),
    InterfaceType.LOOPBACK: InterfaceCapabilities(True, True, False),
    InterfaceType.TUNNEL: InterfaceCapabilities(True, True, False),
    InterfaceType.SUBINTERFACE: InterfaceCapabilities(True, True, False),
}


def qml_metadata(name: Any, profile_kind: Any = "") -> dict[str, Any]:
    interface_type = infer_interface_type(name, profile_kind)
    capability = CAPABILITIES[interface_type]
    return {
        "interface_type": interface_type.value,
        "display_name": short_interface_name(name),
        "is_virtual": interface_type is not InterfaceType.PHYSICAL,
        "can_create": capability.can_create,
        "can_delete": capability.can_delete,
        "can_configure_l1": capability.can_configure_l1,
    }
