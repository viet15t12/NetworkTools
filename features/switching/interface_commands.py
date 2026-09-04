"""Cisco IOS command rendering for physical ports and EtherChannels."""

from __future__ import annotations

import re
from typing import Any


def _is_port_channel(name: Any) -> bool:
    """Return whether an interface name identifies a logical Port-channel."""
    normalized = str(name or "").strip().lower().replace(" ", "")
    return bool(
        normalized.startswith(("port-channel", "portchannel"))
        or re.match(r"^po\d", normalized)
    )


def _render_physical_interface(item: dict[str, Any]) -> list[str]:
    """Render one physical interface, including Layer 2/Layer 3 transitions."""
    commands = [f"interface {item['if_name']}"]
    commands.append(
        f" description {item['description']}" if item["description"] else " no description"
    )
    commands.append(" shutdown" if item["admin_status"] == "down" else " no shutdown")
    if not _is_port_channel(item["if_name"]):
        commands.extend([f" speed {item['speed']}", f" duplex {item['duplex']}"])

    # Port Security must be removed before IOS can convert an access interface
    # into a trunk or a routed port.
    if item.get("disable_port_security"):
        commands.append(" no switchport port-security")

    if item["mode"] == "routed":
        commands.extend([" no switchport", " exit"])
        return commands

    commands.append(" switchport")
    if item["mode"] == "access":
        commands.extend(
            [" switchport mode access", f" switchport access vlan {item['access_vlan']}"]
        )
        if item["voice_vlan"] is not None:
            commands.append(f" switchport voice vlan {item['voice_vlan']}")
        else:
            commands.append(" no switchport voice vlan")
    elif item["mode"] == "trunk":
        commands.extend(
            [
                f" switchport trunk encapsulation {item['encapsulation']}",
                " switchport mode trunk",
                f" switchport trunk native vlan {item['native_vlan']}",
                f" switchport trunk allowed vlan {item['allowed_vlans']}",
            ]
        )
    commands.append(" exit")
    return commands


def _render_etherchannel(channel: dict[str, Any]) -> list[str]:
    """Render one EtherChannel setup or removal operation."""
    commands: list[str] = []
    members = [
        value.strip()
        for value in str(channel["member_ports"] or "").split(",")
        if value.strip()
    ]
    cleanup_members = [
        value.strip()
        for value in str(channel.get("cleanup_member_ports") or "").split(",")
        if value.strip()
    ]
    if channel.get("action") == "remove":
        for member in dict.fromkeys([*members, *cleanup_members]):
            commands.extend([f"interface {member}", " no channel-group", " exit"])
        commands.append(f"no interface Port-channel{channel['po_number']}")
        return commands

    for member in cleanup_members:
        commands.extend([f"interface {member}", " no channel-group", " exit"])
    for member in members:
        commands.extend(
            [
                f"interface {member}",
                f" channel-group {channel['po_number']} mode {channel['mode']}",
                " exit",
            ]
        )
    commands.append(f"interface Port-channel{channel['po_number']}")
    commands.append(
        f" description {channel['description']}"
        if channel["description"]
        else " no description"
    )
    commands.append(" exit")
    return commands


def render_interfaces(payload: dict[str, Any]) -> list[str]:
    """Render all physical-interface and EtherChannel entries in a task."""
    commands: list[str] = []
    for item in payload.get("interfaces", []):
        commands.extend(_render_physical_interface(item))
    for channel in payload.get("etherchannels", []):
        commands.extend(_render_etherchannel(channel))
    return commands


__all__ = ["render_interfaces"]
