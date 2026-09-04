"""Pure verification helpers for Cisco command output and configuration."""

from __future__ import annotations

import re


CLI_ERROR_PATTERN = (
    r"%\s*(?:Invalid input|Incomplete command|Ambiguous command|"
    r"Unknown command|Error)\b"
)
CLI_ERROR_RE = re.compile(CLI_ERROR_PATTERN, re.IGNORECASE)
_INTERFACE_ALIASES = {
    "et": "ethernet", "eth": "ethernet", "fa": "fastethernet",
    "fastethernet": "fastethernet", "gi": "gigabitethernet",
    "gig": "gigabitethernet", "gigabitethernet": "gigabitethernet",
    "te": "tengigabitethernet", "tengigabitethernet": "tengigabitethernet",
    "fo": "fortygigabitethernet", "fortygigabitethernet": "fortygigabitethernet",
    "hu": "hundredgige", "hundredgige": "hundredgige", "lo": "loopback",
    "loopback": "loopback", "po": "port-channel", "port-channel": "port-channel",
    "se": "serial", "serial": "serial", "tu": "tunnel", "tunnel": "tunnel",
    "vl": "vlan", "vlan": "vlan",
}


def contains_cli_error(output: str) -> bool:
    return CLI_ERROR_RE.search(str(output or "")) is not None


def cli_error_detail(output: str) -> str:
    for line in str(output or "").splitlines():
        if contains_cli_error(line):
            return line.strip()
    return "Cisco IOS rejected the command."


def _normalized_line(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_interface(value: str) -> str:
    compact = re.sub(r"\s+", "", str(value or "")).lower()
    match = re.fullmatch(r"([a-z-]+)(.*)", compact)
    if not match:
        return compact
    prefix, suffix = match.groups()
    return _INTERFACE_ALIASES.get(prefix, prefix) + suffix


def interface_exists(output: str, interface: str) -> bool:
    expected = normalize_interface(interface)
    return any(
        fields and normalize_interface(fields[0]) == expected
        for fields in (line.strip().split() for line in output.splitlines())
    )


def verify_destination(
    output: str, server_ip: str, protocol: str, port: int, *, expected: bool,
) -> str | None:
    command = _normalized_line(
        f"logging host {server_ip} transport {protocol.lower()} port {int(port)}"
    )
    present = any(_normalized_line(line) == command for line in output.splitlines())
    if present == expected:
        return None
    state = "does not contain" if expected else "still contains"
    return f"Device configuration {state} '{command}'."


def verify_source_interface(output: str, interface: str) -> bool:
    prefix = "logging source-interface "
    expected = normalize_interface(interface)
    for line in output.splitlines():
        normalized = _normalized_line(line)
        if normalized.startswith(prefix):
            configured = normalized[len(prefix):].split()[0]
            if normalize_interface(configured) == expected:
                return True
    return False


__all__ = [
    "CLI_ERROR_PATTERN", "cli_error_detail", "contains_cli_error", "interface_exists",
    "normalize_interface", "verify_destination", "verify_source_interface",
]
