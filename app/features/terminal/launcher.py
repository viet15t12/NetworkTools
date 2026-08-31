"""Discovery and QProcess launch specification for CAMS Terminal."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QObject, QProcess

from .ssh import (
    TerminalLaunchError,
    build_terminal_command,
    sanitize_display_text,
    validate_host,
)


@dataclass(frozen=True, slots=True)
class TerminalLaunchSpec:
    """Program and argv passed directly to ``QProcess.start``."""

    program: str
    arguments: tuple[str, ...]
    title: str


class TerminalLauncher:
    """Locate the companion binary and build a managed launch contract."""

    def __init__(
        self,
        binary: str | Path | None = None,
        *,
        process_factory: Callable[[QObject | None], Any] = QProcess,
    ) -> None:
        self._configured_binary = str(binary or "").strip()
        self._process_factory = process_factory

    def resolve_binary(self) -> str:
        """Return an executable companion path or raise an actionable error."""
        configured = self._configured_binary or os.environ.get(
            "NETWORKTOOLS_TERMINAL_BINARY", ""
        ).strip()
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
            raise TerminalLaunchError(
                "Configured CAMS Terminal binary is missing or not executable."
            )
        discovered = shutil.which("networktools-terminal")
        if discovered:
            return discovered
        bundled = (
            Path(__file__).resolve().parents[2]
            / "vendor"
            / "alacritty"
            / "target"
            / "release"
            / ("networktools-terminal.exe" if os.name == "nt" else "networktools-terminal")
        )
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
        raise TerminalLaunchError(
            "CAMS Terminal is not installed, built in vendor/alacritty, "
            "or available on PATH."
        )

    def create_process(self, parent: QObject | None) -> Any:
        """Create the QProcess-like object used for one session."""
        return self._process_factory(parent)

    def build_spec(
        self,
        device: dict[str, Any],
        *,
        session_id: str,
        device_id: str,
        ipc_path: str,
    ) -> TerminalLaunchSpec:
        """Build managed metadata and an OpenSSH child without any secret."""
        host = validate_host(device.get("host"))
        name = sanitize_display_text(
            device.get("device_name"), fallback=host, limit=80
        )
        title = sanitize_display_text(
            f"{name} — CAMS", fallback="CAMS Terminal", limit=128
        )
        ssh = build_terminal_command(device)
        arguments = (
            "--nt-managed",
            "--nt-session-id",
            session_id,
            "--nt-device-id",
            str(device_id),
            "--nt-device-name",
            name,
            "--nt-host",
            host,
            "--nt-ipc",
            ipc_path,
            "--title",
            title,
            "-e",
            ssh.program,
            *ssh.arguments,
        )
        return TerminalLaunchSpec(
            program=self.resolve_binary(),
            arguments=arguments,
            title=title,
        )
