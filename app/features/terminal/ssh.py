"""Safe OpenSSH launch arguments for an interactive terminal child."""

from __future__ import annotations

import ipaddress
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
ALGORITHM_RE = re.compile(r"^[A-Za-z0-9@._+-]+$")
LEGACY_CISCO_IOS_ALGORITHMS = {
    "kex": ("diffie-hellman-group14-sha1", "diffie-hellman-group-exchange-sha1"),
    "key_types": ("ssh-rsa",),
}


class TerminalLaunchError(ValueError):
    """Raised when inventory metadata cannot produce a safe launch."""


@dataclass(frozen=True, slots=True)
class OpenSshCommand:
    """Executable and argument list passed after Alacritty's ``-e`` flag."""

    program: str
    arguments: tuple[str, ...]


def sanitize_display_text(value: Any, *, fallback: str, limit: int = 80) -> str:
    """Remove control characters and bound untrusted window metadata."""
    cleaned = "".join(
        " " if str(character).isspace() else str(character)
        for character in str(value or "")
        if not unicodedata.category(character).startswith("C")
    )
    cleaned = " ".join(cleaned.split()).strip()
    return (cleaned or fallback)[:limit]


def validate_host(value: Any) -> str:
    """Return a validated IP literal or conservative DNS hostname."""
    host = str(value or "").strip()
    if not host or len(host) > 253 or host.startswith("-"):
        raise TerminalLaunchError("The terminal host is missing or invalid.")
    if any(character.isspace() or ord(character) < 32 for character in host):
        raise TerminalLaunchError("The terminal host contains unsafe characters.")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if not all(HOST_LABEL_RE.fullmatch(label) for label in host.rstrip(".").split(".")):
        raise TerminalLaunchError("The terminal host is not a valid IP address or hostname.")
    return host


def validate_username(value: Any) -> str:
    """Return a conservative OpenSSH username suitable for ``user@host``."""
    username = str(value or "").strip()
    if not USERNAME_RE.fullmatch(username):
        raise TerminalLaunchError(
            "The SSH username is missing or contains unsupported characters."
        )
    return username


def validate_port(value: Any) -> int:
    """Return a TCP port in the user-addressable range."""
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise TerminalLaunchError("The SSH port is invalid.") from exc
    if not 1 <= port <= 65535:
        raise TerminalLaunchError("The SSH port must be between 1 and 65535.")
    return port


def build_openssh_command(device: dict[str, Any]) -> OpenSshCommand:
    """Build an argument-only OpenSSH command without copying credentials."""
    method = str(device.get("method") or "ssh").strip().lower()
    if method != "ssh":
        raise TerminalLaunchError(
            "CAMS Terminal currently supports managed OpenSSH sessions only."
        )
    host = validate_host(device.get("host"))
    username = validate_username(device.get("username"))
    port = validate_port(device.get("port") or 22)
    algorithms = _openssh_algorithms(device)
    options: list[str] = []
    option_names = {
        "kex": "KexAlgorithms",
        "key_types": "HostKeyAlgorithms",
        "ciphers": "Ciphers",
        "digests": "MACs",
    }
    for group, option_name in option_names.items():
        values = algorithms.get(group, ())
        if values:
            options.extend(("-o", f"{option_name}={','.join(values)}"))
    # Old Cisco IOS commonly signs its host key with ssh-rsa/SHA-1. Fedora's
    # OpenSSH filters it from the host-key proposal unless both lists are set.
    key_types = algorithms.get("key_types", ())
    if "ssh-rsa" in key_types:
        options.extend(("-o", f"PubkeyAcceptedAlgorithms={','.join(key_types)}"))
    return OpenSshCommand(
        program="ssh",
        arguments=(*options, "-p", str(port), f"{username}@{host}"),
    )


def build_terminal_command(device: dict[str, Any]) -> OpenSshCommand:
    """Select OpenSSH or the isolated legacy Cisco interactive adapter."""
    if str(device.get("device_type") or "").strip().lower() != "cisco_ios":
        return build_openssh_command(device)
    host = validate_host(device.get("host"))
    db_path = Path(str(device.get("db_path") or "")).expanduser()
    if not db_path.is_file():
        raise TerminalLaunchError("The active workspace database is unavailable.")
    adapter = Path(__file__).resolve().with_name("interactive_ssh.py")
    return OpenSshCommand(
        program=sys.executable,
        arguments=("-u", str(adapter), "--db", str(db_path.resolve()), "--host", host),
    )


def _openssh_algorithms(device: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Return safe per-host overrides, with a bounded Cisco IOS lab fallback."""
    raw = device.get("ssh_algorithms")
    normalized: dict[str, tuple[str, ...]] = {}
    if isinstance(raw, dict):
        for group in ("kex", "key_types", "ciphers", "digests"):
            values = raw.get(group, ())
            if isinstance(values, str):
                values = values.split(",")
            if isinstance(values, (list, tuple)):
                cleaned = tuple(
                    value
                    for item in values
                    if (value := str(item or "").strip()) and ALGORITHM_RE.fullmatch(value)
                )
                if cleaned:
                    normalized[group] = tuple(dict.fromkeys(cleaned))
    if normalized:
        return normalized
    if str(device.get("device_type") or "").strip().lower() == "cisco_ios":
        return dict(LEGACY_CISCO_IOS_ALGORITHMS)
    return {}
