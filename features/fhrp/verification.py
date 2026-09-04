"""Post-command verification for Cisco IOS FHRP member tasks."""

from __future__ import annotations

from typing import Any


_CLI_ERROR_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "% unknown command",
    "% error",
)

_SHOW_COMMANDS = {
    "hsrp": "show standby brief",
    "vrrp": "show vrrp brief",
    "glbp": "show glbp brief",
}


def _checked_show(connection: Any, command: str) -> str:
    sender = getattr(connection, "send_command", None)
    if not callable(sender):
        raise RuntimeError("Device session cannot run FHRP verification commands")
    output = str(sender(command, read_timeout=60) or "")
    lowered = output.lower()
    if any(marker in lowered for marker in _CLI_ERROR_MARKERS):
        raise RuntimeError(output.strip() or f"Cisco IOS rejected {command}")
    return output


def _activation_line(config: dict[str, Any]) -> str:
    protocol = str(config["protocol"])
    keyword = {"hsrp": "standby", "vrrp": "vrrp", "glbp": "glbp"}[protocol]
    return f"{keyword} {config['group_number']} ip {config['virtual_ip']}".lower()


def verify_fhrp_task(
    connection: Any,
    task: dict[str, Any],
    *,
    show_cache: dict[str, str] | None = None,
) -> str:
    """Require desired running config and an operational group before DB sync."""
    config = task.get("config") or {}
    interface_name = str(config.get("interface_name") or "").strip()
    protocol = str(config.get("protocol") or "").strip().lower()
    if not interface_name or protocol not in _SHOW_COMMANDS:
        raise RuntimeError("FHRP task is missing interface or protocol identity")

    def show(command: str) -> str:
        """Reuse identical show output while verifying one host batch."""
        if show_cache is not None and command in show_cache:
            return show_cache[command]
        output = _checked_show(connection, command)
        if show_cache is not None:
            show_cache[command] = output
        return output

    running = show(f"show running-config interface {interface_name}")
    normalized_running = {
        " ".join(line.strip().lower().split()) for line in running.splitlines()
    }
    activation = _activation_line(config)
    action = str(task.get("action") or "setup").lower()
    if action == "remove":
        keyword = {"hsrp": "standby", "vrrp": "vrrp", "glbp": "glbp"}[protocol]
        group_prefix = f"{keyword} {config['group_number']} "
        residual = sorted(
            line for line in normalized_running if line.startswith(group_prefix)
        )
        if residual:
            raise RuntimeError(
                f"FHRP removal verification failed on {interface_name}: "
                "group policy remains in running-config"
            )
        return "Running-config confirms the complete FHRP group policy was removed."

    if activation not in normalized_running:
        raise RuntimeError(
            f"FHRP verification failed on {interface_name}: activation line is missing"
        )
    operational = show(_SHOW_COMMANDS[protocol])
    virtual_ip = str(config.get("virtual_ip") or "")
    if virtual_ip not in operational:
        raise RuntimeError(
            f"{protocol.upper()} operational verification did not find {virtual_ip}"
        )
    return f"Running-config and {protocol.upper()} operational state verified."


__all__ = ["verify_fhrp_task"]
