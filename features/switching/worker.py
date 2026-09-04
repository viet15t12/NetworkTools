from __future__ import annotations

from typing import Any

from .cli_validation import has_rejected_command


# Backward-compatible private name retained for focused unit tests and callers.
_has_rejected_command = has_rejected_command


def apply_commands(connector: Any, commands: list[str]) -> str:
    connection = getattr(connector, "connection", None)
    if connection is None:
        raise RuntimeError("The active device session is unavailable")
    output = str(
        connection.send_config_set(commands, read_timeout=60, cmd_verify=False)
    )
    if has_rejected_command(output):
        raise RuntimeError(output.strip() or "The switch rejected the configuration")
    return output
