"""Cisco session I/O for applying, reading, and saving Syslog configuration."""

from __future__ import annotations

from typing import Any

from features.devices.save_config_service import SaveConfigService

from .verifier import CLI_ERROR_PATTERN, cli_error_detail, contains_cli_error, interface_exists


class CiscoSyslogWorker:
    def __init__(self, connector: Any) -> None:
        self.connector = connector
        self.connection = getattr(connector, "connection", None)
        if self.connection is None:
            raise RuntimeError("The active device session has no CLI connection")

    def send(self, commands: list[str]) -> str:
        output = str(self.connection.send_config_set(
            commands,
            read_timeout=60,
            cmd_verify=False,
            error_pattern=CLI_ERROR_PATTERN,
        ) or "")
        if contains_cli_error(output):
            raise RuntimeError(
                f"Cisco CLI rejected the Syslog command: {cli_error_detail(output)}"
            )
        return output

    def show_logging(self, *, startup: bool) -> str:
        config = "startup-config" if startup else "running-config"
        output = str(self.connection.send_command(f"show {config} | include logging") or "")
        if contains_cli_error(output):
            raise RuntimeError(f"Could not read {config}: {cli_error_detail(output)}")
        return output

    def save(self) -> str:
        output = SaveConfigService.copy_running_to_startup(self.connector)
        if contains_cli_error(output):
            raise RuntimeError(
                "copy running-config startup-config failed: " + cli_error_detail(output)
            )
        return output

    def interface_exists(self, interface: str) -> bool:
        output = str(self.connection.send_command("show ip interface brief") or "")
        if contains_cli_error(output):
            raise RuntimeError(
                "Could not validate source interface: " + cli_error_detail(output)
            )
        return interface_exists(output, interface)


__all__ = ["CiscoSyslogWorker"]
