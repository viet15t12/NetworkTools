"""Pure Cisco IOS/IOS-XE Syslog command generation."""

from __future__ import annotations

import re
from ipaddress import ip_address


SEVERITY_WORDS = (
    "emergencies", "alerts", "critical", "errors",
    "warnings", "notifications", "informational", "debugging",
)
INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9./:_-]{0,63}$")


def _validate_destination(server_ip: str, protocol: str, port: int) -> str:
    address = ip_address(server_ip)
    if address.is_unspecified:
        raise ValueError("Syslog server IP cannot be unspecified")
    protocol = protocol.lower()
    if protocol not in {"udp", "tcp"}:
        raise ValueError("Unsupported syslog transport")
    if not 1 <= int(port) <= 65535:
        raise ValueError("Invalid syslog port")
    return protocol


def build_enable_commands(
    server_ip: str, protocol: str, port: int, source_interface: str,
    trap_severity: int = 5, timestamps: bool = False,
    sequence_numbers: bool = False,
) -> list[str]:
    protocol = _validate_destination(server_ip, protocol, port)
    source_interface = source_interface.strip()
    if not INTERFACE_RE.fullmatch(source_interface):
        raise ValueError("Source interface contains unsupported characters")
    if not 0 <= trap_severity <= 7:
        raise ValueError("Severity must be between 0 and 7")
    commands = [
        f"logging host {server_ip} transport {protocol} port {port}",
        f"logging trap {SEVERITY_WORDS[trap_severity]}",
    ]
    if timestamps:
        commands.append("service timestamps log datetime msec")
    if sequence_numbers:
        commands.append("service sequence-numbers")
    commands.append(f"logging source-interface {source_interface}")
    return commands


def build_cancel_commands(server_ip: str, protocol: str, port: int) -> list[str]:
    protocol = _validate_destination(server_ip, protocol, port)
    return [f"no logging host {server_ip} transport {protocol} port {port}"]


__all__ = ["build_cancel_commands", "build_enable_commands"]
