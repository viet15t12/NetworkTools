"""Download a Cisco running-config through a bounded SCP workflow.

NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import paramiko
from scp import SCPClient

from infrastructure.network.netmiko_factory import connect_device

from .sftp_service import (
    CaptureHostKeyPolicy,
    ConfirmedHostKeyPolicy,
    ConnectionOptions,
    UnknownHostKeyError,
)


_CLI_ERROR_MARKERS = (
    "% invalid input",
    "% incomplete command",
    "% ambiguous command",
    "% unknown command",
    "% error",
    "error opening",
    "no space left",
)
_COPY_PROMPTS = ("destination filename", "[confirm]", "overwrite")


def _safe_host(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()) or "device"


def _check_cli_output(output: Any, operation: str) -> str:
    text = str(output or "")
    lowered = text.lower()
    if any(marker in lowered for marker in _CLI_ERROR_MARKERS):
        raise RuntimeError(f"{operation} failed: {text.strip() or 'device rejected command'}")
    return text


class ScpRunningConfigService:
    """Enable Cisco SCP when needed and atomically download a temporary config."""

    def __init__(
        self,
        *,
        ssh_client_factory: Callable[[], Any] = paramiko.SSHClient,
        cli_connect: Callable[[dict[str, Any]], Any] | None = None,
        scp_client_factory: Callable[..., Any] = SCPClient,
        known_hosts_path: Path | None = None,
    ) -> None:
        self._ssh_client_factory = ssh_client_factory
        self._cli_connect = cli_connect or (lambda params: connect_device(params))
        self._scp_client_factory = scp_client_factory
        self._known_hosts_path = known_hosts_path or Path.home() / ".ssh" / "known_hosts"
        self._pending_host_key: dict[str, str] | None = None

    @property
    def pending_host_key(self) -> dict[str, str] | None:
        return dict(self._pending_host_key) if self._pending_host_key else None

    def download(
        self,
        options: ConnectionOptions,
        local_directory: str,
        accepted_fingerprint: str = "",
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        destination_dir = Path(local_directory).expanduser().resolve()
        if not destination_dir.is_dir():
            raise ValueError("The selected local SCP directory does not exist")

        self._pending_host_key = None
        ssh = self._open_ssh(options, accepted_fingerprint)
        cli = None
        remote_path = f"flash:/cams-running-{uuid4().hex[:10]}.cfg"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = destination_dir / (
            f"{_safe_host(options.host)}_running-config_{timestamp}.cfg"
        )
        partial = destination.with_name(destination.name + ".part")
        enabled_scp = False
        cleanup_warning = ""
        try:
            cli = self._open_cli(options)
            show_output = _check_cli_output(
                cli.send_command(
                    "show running-config | include ^ip scp server enable"
                ),
                "Check SCP server state",
            )
            if "ip scp server enable" not in show_output.lower():
                enable_output = cli.send_config_set(["ip scp server enable"])
                _check_cli_output(enable_output, "Enable SCP server")
                self._save_cli_config(cli)
                enabled_scp = True

            copy_output = self._copy_running_to_flash(cli, remote_path)
            _check_cli_output(copy_output, "Create temporary running-config")

            def report(filename: bytes, size: int, sent: int) -> None:
                del filename
                if progress is not None:
                    progress(int(sent), int(size))

            transport = ssh.get_transport()
            if transport is None or not transport.is_active():
                raise RuntimeError("The SCP SSH transport is unavailable")
            with self._scp_client_factory(transport, progress=report) as client:
                client.get(remote_path, str(partial))
            if not partial.is_file() or partial.stat().st_size <= 0:
                raise RuntimeError("SCP returned an empty running-config file")
            partial.replace(destination)
        finally:
            if cli is not None:
                try:
                    cleanup_output = cli.send_command_timing(
                        f"delete /force {remote_path}",
                        strip_prompt=False,
                        strip_command=False,
                    )
                    _check_cli_output(cleanup_output, "Remove temporary config")
                except Exception as exc:
                    cleanup_warning = str(exc)
                try:
                    cli.disconnect()
                except Exception:
                    pass
            try:
                ssh.close()
            except Exception:
                pass
            if partial.exists():
                partial.unlink(missing_ok=True)

        return {
            "ok": True,
            "host": options.host,
            "localPath": str(destination),
            "scpEnabled": enabled_scp,
            "cleanupWarning": cleanup_warning,
            "message": (
                f"Running-config downloaded via SCP to {destination}."
                + (
                    " SCP server was enabled and saved on the device."
                    if enabled_scp
                    else ""
                )
                + (
                    f" Warning: {cleanup_warning}"
                    if cleanup_warning
                    else ""
                )
            ),
        }

    def _open_ssh(
        self, options: ConnectionOptions, accepted_fingerprint: str
    ) -> Any:
        ssh = self._ssh_client_factory()
        ssh.load_system_host_keys()
        if self._known_hosts_path.exists():
            ssh.load_host_keys(str(self._known_hosts_path))
        policy = (
            ConfirmedHostKeyPolicy(
                accepted_fingerprint,
                self._known_hosts_path,
            )
            if accepted_fingerprint
            else CaptureHostKeyPolicy()
        )
        ssh.set_missing_host_key_policy(policy)
        arguments: dict[str, Any] = {
            "hostname": options.host,
            "port": options.port,
            "username": options.username,
            "password": options.password or None,
            "timeout": options.timeout,
            "banner_timeout": options.timeout,
            "auth_timeout": options.timeout,
            "look_for_keys": not bool(options.private_key),
            "allow_agent": True,
        }
        if options.private_key:
            arguments["key_filename"] = options.private_key
        try:
            ssh.connect(**arguments)
        except UnknownHostKeyError as exc:
            self._pending_host_key = exc.info
            ssh.close()
            raise
        except Exception:
            ssh.close()
            raise
        return ssh

    def _open_cli(self, options: ConnectionOptions) -> Any:
        params: dict[str, Any] = {
            "device_type": "cisco_ios",
            "host": options.host,
            "port": options.port,
            "username": options.username,
            "password": options.password,
            "secret": options.password,
            "conn_timeout": options.timeout,
            "auth_timeout": options.timeout,
            "banner_timeout": options.timeout,
            "blocking_timeout": options.timeout,
            "ssh_strict": True,
            "system_host_keys": True,
            "alt_host_keys": True,
            "alt_key_file": str(self._known_hosts_path),
            "allow_agent": True,
            "use_keys": bool(options.private_key),
        }
        if options.private_key:
            params["key_file"] = options.private_key
        return self._cli_connect(params)

    @staticmethod
    def _save_cli_config(cli: Any) -> str:
        output = cli.save_config(
            cmd="copy running-config startup-config",
            confirm=True,
        )
        return _check_cli_output(output, "Save SCP server configuration")

    @staticmethod
    def _copy_running_to_flash(cli: Any, remote_path: str) -> str:
        output = str(
            cli.send_command_timing(
                f"copy running-config {remote_path}",
                strip_prompt=False,
                strip_command=False,
            )
            or ""
        )
        for _ in range(2):
            if not any(prompt in output.lower() for prompt in _COPY_PROMPTS):
                break
            output += str(
                cli.send_command_timing(
                    "",
                    strip_prompt=False,
                    strip_command=False,
                )
                or ""
            )
        return output


__all__ = ["ScpRunningConfigService"]
