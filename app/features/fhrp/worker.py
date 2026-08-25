"""Send rendered FHRP commands through an app-owned device session."""

from __future__ import annotations

from typing import Any, Callable

from .commands import redact_fhrp_commands, redact_fhrp_output, render_fhrp_commands
from .verification import verify_fhrp_task


_CLI_ERROR_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "% unknown command",
    "% error",
)


def _check_cli_output(output: Any) -> str:
    text = str(output or "")
    lowered = text.lower()
    if any(marker in lowered for marker in _CLI_ERROR_MARKERS):
        raise RuntimeError(text.strip() or "Cisco IOS rejected the FHRP command")
    return text


def push_fhrp_tasks(
    tasks: list[dict[str, Any]],
    template_folder: str,
    session_provider: Callable[[str], Any],
) -> list[dict[str, Any]]:
    """Push tasks independently and return one report item per FHRP member."""
    reports: list[dict[str, Any]] = []
    for task in tasks:
        host = str(task.get("target", {}).get("ip") or "")
        config = task.get("config") or {}
        commands = render_fhrp_commands(task, template_folder)
        try:
            connector = session_provider(host)
            if connector is None:
                raise RuntimeError("No active device session is available")
            connection = getattr(connector, "connection", connector)
            output = _check_cli_output(
                connection.send_config_set(
                    commands,
                    read_timeout=120,
                    cmd_verify=False,
                )
            )
            verification = verify_fhrp_task(connection, task)
            reports.append(
                {
                    "host": host,
                    "member_id": config.get("member_id"),
                    "status": "SUCCESS",
                    "commands": redact_fhrp_commands(commands),
                    "log": "\n".join(
                        part
                        for part in (redact_fhrp_output(output, task), verification)
                        if part
                    ),
                    "task": task,
                }
            )
        except Exception as exc:
            reports.append(
                {
                    "host": host,
                    "member_id": config.get("member_id"),
                    "status": "FAILED",
                    "commands": redact_fhrp_commands(commands),
                    "log": redact_fhrp_output(str(exc), task),
                    "task": task,
                }
            )
    return reports
