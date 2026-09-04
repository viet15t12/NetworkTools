"""Send rendered router-interface commands through an app-owned session."""

from __future__ import annotations

from typing import Any


_ERROR_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "% authorization failed",
)


def apply_interface_commands(connector: Any, commands: list[str]) -> str:
    """Apply one command batch and reject common Cisco CLI error responses."""
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("The active device session is unavailable")
    output = str(
        connection.send_config_set(commands, read_timeout=60, cmd_verify=False)
    )
    normalized = output.lower()
    if any(marker in normalized for marker in _ERROR_MARKERS):
        raise RuntimeError(output.strip() or "The router rejected the interface configuration")
    return output


__all__ = ["apply_interface_commands"]
