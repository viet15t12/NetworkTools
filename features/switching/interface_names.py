"""Normalization helpers shared by switch operational-state parsers."""

from __future__ import annotations

import re


INTERFACE_NAME_PATTERN = r"[A-Za-z][A-Za-z-]*\d+(?:/\d+)*"

_PREFIXES = {
    "gi": "GigabitEthernet",
    "fa": "FastEthernet",
    "te": "TenGigabitEthernet",
    "eth": "Ethernet",
    "po": "Port-channel",
    "port-channel": "Port-channel",
    "portchannel": "Port-channel",
}


def normalize_interface_name(value: str) -> str:
    """Expand a common IOS interface abbreviation to the canonical name."""
    name = str(value or "").strip()
    match = re.match(r"^([A-Za-z][A-Za-z-]*)(\d.*)$", name)
    if not match:
        return name
    return _PREFIXES.get(match.group(1).lower(), match.group(1)) + match.group(2)


__all__ = ["INTERFACE_NAME_PATTERN", "normalize_interface_name"]
