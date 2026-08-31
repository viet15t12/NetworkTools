"""State owned by one externally rendered CAMS Terminal session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ProcessState(StrEnum):
    """Lifecycle of the operating-system terminal process."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class WindowState(StrEnum):
    """Lifecycle reported by the terminal window over NTTP."""

    CLOSED = "closed"
    STARTING = "starting"
    OPEN = "open"
    CLOSING = "closing"
    ERROR = "error"


class IpcState(StrEnum):
    """State of the terminal's local NTTP connection."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class ChildState(StrEnum):
    """State of the OpenSSH child inside the terminal process."""

    UNKNOWN = "unknown"
    RUNNING = "running"
    EXITED = "exited"


@dataclass(slots=True)
class TerminalSession:
    """Metadata and orthogonal state for one managed terminal process.

    Credentials deliberately do not belong to this object. ``session_id`` is
    the application identity; the operating-system PID may be reused.
    """

    session_id: str
    device_id: str
    device_name: str
    host: str
    username: str
    port: int
    title: str
    process: Any | None = None
    pid: int | None = None
    process_state: ProcessState = ProcessState.STARTING
    window_state: WindowState = WindowState.STARTING
    ipc_state: IpcState = IpcState.DISCONNECTED
    child_state: ChildState = ChildState.UNKNOWN
    child_pid: int | None = None
    child_exit_code: int | None = None
    terminal_closed_received: bool = False
    close_requested: bool = False
    restart_requested: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    last_error: str = ""

    @property
    def ui_state(self) -> str:
        """Return the small aggregate state exposed to QML."""
        if (
            self.process_state is ProcessState.ERROR
            or self.window_state is WindowState.ERROR
            or self.ipc_state is IpcState.ERROR
        ):
            return "error"
        if self.window_state is WindowState.OPEN:
            if self.child_state is ChildState.EXITED:
                return "disconnected"
            return "open"
        if (
            self.process_state is ProcessState.STARTING
            or self.window_state is WindowState.STARTING
        ):
            return "starting"
        return "closed"

