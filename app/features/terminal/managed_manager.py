"""Managed external NetworkTools Terminal lifecycle and device registry."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from .ipc_server import NttpServer
from .launcher import TerminalLauncher
from .session import (
    ChildState,
    IpcState,
    ProcessState,
    TerminalSession,
    WindowState,
)
from .ssh import TerminalLaunchError, sanitize_display_text, validate_port


class ManagedTerminalManager(QObject):
    """Own one externally rendered terminal session per inventory host."""

    terminalStateChanged = pyqtSignal(str, str)
    terminalError = pyqtSignal(str, str)

    def __init__(
        self,
        device_loader: Any,
        parent: QObject | None = None,
        *,
        launcher: TerminalLauncher | None = None,
        ipc_server: NttpServer | None = None,
        close_timeout_ms: int = 3000,
    ) -> None:
        super().__init__(parent)
        self._device_loader = device_loader
        self._launcher = launcher or TerminalLauncher()
        self._ipc = ipc_server or NttpServer(self)
        self._close_timeout_ms = max(1, int(close_timeout_ms))
        self.sessions_by_id: dict[str, TerminalSession] = {}
        self.device_session: dict[str, str] = {}
        self._last_states: dict[str, str] = {}
        self._shutting_down = False

        self._ipc.eventReceived.connect(self.handle_terminal_event)
        self._ipc.sessionConnected.connect(self._ipc_connected)
        self._ipc.sessionDisconnected.connect(self._ipc_disconnected)
        self._ipc.requestTimedOut.connect(self._command_timed_out)
        self._ipc.protocolError.connect(self._protocol_error)

    def open(self, host: str) -> dict[str, Any]:
        """Start a managed OpenSSH terminal or focus the existing session."""
        host = str(host or "").strip()
        if not host:
            return self._result(False, "warning", "Select a device before opening CLI.")
        if self._shutting_down:
            return self._result(False, "error", "The terminal manager is shutting down.")

        existing = self.session_for_device(host)
        if existing is not None:
            if existing.ui_state == "open":
                # Graceful degradation: an IPC outage must not destroy a live
                # human terminal merely because a second click cannot focus it.
                return self.focus(host)
            if existing.ui_state == "starting":
                return self._result(
                    True,
                    "info",
                    f"NetworkTools Terminal is already starting for {host}.",
                    state="starting",
                )
            existing.restart_requested = True
            self._stop_process(existing)
            return self._result(
                True,
                "info",
                f"Restarting NetworkTools Terminal for {host}.",
                state="starting",
            )

        try:
            device = self._load_device(host)
            ipc_path = self._ipc.start()
            session_id = str(uuid4())
            device_id = str(device.get("device_id") or host)
            spec = self._launcher.build_spec(
                device,
                session_id=session_id,
                device_id=device_id,
                ipc_path=ipc_path,
            )
            process = self._launcher.create_process(self)
            device_name = sanitize_display_text(
                device.get("device_name"), fallback=host, limit=80
            )
            session = TerminalSession(
                session_id=session_id,
                device_id=device_id,
                device_name=device_name,
                host=host,
                username=str(device.get("username") or ""),
                port=validate_port(device.get("port") or 22),
                title=spec.title,
                process=process,
            )
        except (RuntimeError, TerminalLaunchError, OSError) as exc:
            return self._fail_open(host, str(exc))

        self.sessions_by_id[session_id] = session
        self.device_session[host] = session_id
        self._ipc.register_session(session_id)
        self._connect_process(session)
        self._set_state(session, "starting", force=True)
        process.start(spec.program, list(spec.arguments))
        return self._result(
            True,
            "success",
            f"Starting NetworkTools Terminal for {device_name}.",
            state="starting",
            sessionId=session_id,
        )

    def focus(self, host: str) -> dict[str, Any]:
        """Ask an existing managed terminal to request window activation."""
        session = self.session_for_device(host)
        if session is None:
            return self._result(False, "warning", f"No terminal is open for {host}.")
        if session.ui_state == "starting":
            return self._result(
                True,
                "info",
                f"NetworkTools Terminal is still starting for {host}.",
                state="starting",
            )
        request_id = self._ipc.send_command(session.session_id, "window.focus")
        if request_id is None:
            return self._result(
                False,
                "warning",
                "The terminal process is running, but its control channel is unavailable.",
                state=session.ui_state,
            )
        return self._result(
            True,
            "success",
            f"Requested focus for NetworkTools Terminal on {host}.",
            state=session.ui_state,
            requestId=request_id,
        )

    def close(self, host: str) -> dict[str, Any]:
        """Request a graceful window close, with a bounded process fallback."""
        session = self.session_for_device(host)
        if session is None:
            self._set_last_state(str(host or "").strip(), "closed")
            return self._result(True, "info", f"No terminal is open for {host}.")
        session.close_requested = True
        session.window_state = WindowState.CLOSING
        self._set_state(session, "closed", force=True)
        request_id = self._ipc.send_command(session.session_id, "window.close")
        if request_id is None:
            self._stop_process(session)
        else:
            QTimer.singleShot(
                self._close_timeout_ms,
                lambda target=session.session_id: self._close_fallback(target),
            )
        return self._result(
            True,
            "success",
            f"Closing NetworkTools Terminal for {host}.",
            state="closed",
            requestId=request_id or "",
        )

    def restart(self, host: str) -> dict[str, Any]:
        """Close the current process and launch a fresh session afterwards."""
        session = self.session_for_device(host)
        if session is None:
            return self.open(host)
        session.restart_requested = True
        result = self.close(host)
        return {
            **result,
            "message": f"Restarting NetworkTools Terminal for {host}.",
            "state": "starting",
        }

    def set_title(self, host: str, title: str) -> dict[str, Any]:
        """Set bounded window metadata through the NTTP command channel."""
        session = self.session_for_device(host)
        if session is None:
            return self._result(False, "warning", f"No terminal is open for {host}.")
        cleaned = sanitize_display_text(title, fallback=session.title, limit=128)
        request_id = self._ipc.send_command(
            session.session_id,
            "window.set_title",
            {"title": cleaned},
        )
        if request_id is None:
            return self._result(False, "warning", "Terminal control channel is unavailable.")
        session.title = cleaned
        return self._result(
            True,
            "success",
            "Terminal title update requested.",
            requestId=request_id,
        )

    def ping(self, host: str) -> dict[str, Any]:
        """Request a bounded liveness response from one terminal session."""
        return self._simple_command(host, "session.ping", "Terminal ping requested.")

    def get_info(self, host: str) -> dict[str, Any]:
        """Request non-sensitive runtime metadata from one terminal session."""
        return self._simple_command(
            host,
            "session.get_info",
            "Terminal session information requested.",
        )

    def is_running(self, host: str) -> bool:
        """Return whether a terminal process is starting or running."""
        session = self.session_for_device(host)
        return bool(
            session is not None
            and session.process_state in {ProcessState.STARTING, ProcessState.RUNNING}
        )

    def state_for_device(self, host: str) -> str:
        """Return one aggregate state suitable for QML."""
        host = str(host or "").strip()
        session = self.session_for_device(host)
        return session.ui_state if session is not None else self._last_states.get(host, "closed")

    def session_for_device(self, host: str) -> TerminalSession | None:
        """Resolve a host through session identity rather than process identity."""
        session_id = self.device_session.get(str(host or "").strip())
        return self.sessions_by_id.get(session_id) if session_id is not None else None

    def handle_terminal_event(self, message: object) -> None:
        """Apply one validated NTTP event to orthogonal session state."""
        if not isinstance(message, dict):
            return
        session = self.sessions_by_id.get(str(message.get("session_id") or ""))
        if session is None:
            return
        event = str(message.get("event") or "")
        data = message.get("data") if isinstance(message.get("data"), dict) else {}
        session.ipc_state = IpcState.CONNECTED
        if event == "terminal.started":
            session.pid = self._positive_int(data.get("pid")) or session.pid
        elif event == "terminal.ready":
            session.window_state = WindowState.OPEN
        elif event == "child.started":
            session.child_state = ChildState.RUNNING
            session.child_pid = self._positive_int(data.get("pid"))
        elif event == "child.exited":
            session.child_state = ChildState.EXITED
            session.child_exit_code = self._integer(data.get("exit_code"))
        elif event == "terminal.closed":
            session.terminal_closed_received = True
            session.window_state = WindowState.CLOSED
        elif event == "terminal.error":
            session.window_state = WindowState.ERROR
            session.last_error = str(data.get("message") or "Terminal reported an error.")
            self.terminalError.emit(session.host, session.last_error)
        self._set_state(session, session.ui_state)

    def shutdown(self, timeout_ms: int = 1500) -> None:
        """Gracefully close managed terminals, then stop the local IPC server."""
        self._shutting_down = True
        sessions = list(self.sessions_by_id.values())
        for session in sessions:
            session.close_requested = True
            if self._ipc.send_command(session.session_id, "window.close") is None:
                self._stop_process(session)
        wait_per_process = max(0, int(timeout_ms)) // max(1, len(sessions))
        for session in sessions:
            process = session.process
            if process is None or session.process_state is ProcessState.STOPPED:
                continue
            wait = getattr(process, "waitForFinished", None)
            if callable(wait) and wait_per_process:
                wait(wait_per_process)
            if session.session_id in self.sessions_by_id:
                self._stop_process(session, kill=True)
        self._ipc.stop()

    def _load_device(self, host: str) -> dict[str, Any]:
        device = self._device_loader(host)
        if not isinstance(device, dict):
            raise TerminalLaunchError(f"Device {host} was not found.")
        if int(device.get("dev") or 0) == 1:
            raise TerminalLaunchError(
                f"{host} is in development mode, which disables real SSH. "
                "Switch to Live Connection before opening the terminal."
            )
        return device

    def _connect_process(self, session: TerminalSession) -> None:
        process = session.process
        process.started.connect(
            lambda target=session.session_id: self._process_started(target)
        )
        process.finished.connect(
            lambda code, status, target=session.session_id: self._process_finished(
                target, code, status
            )
        )
        process.errorOccurred.connect(
            lambda error, target=session.session_id: self._process_error(target, error)
        )

    def _process_started(self, session_id: str) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is None:
            return
        session.process_state = ProcessState.RUNNING
        process_id = getattr(session.process, "processId", None)
        session.pid = self._positive_int(process_id()) if callable(process_id) else None
        self._set_state(session, session.ui_state)

    def _process_finished(self, session_id: str, exit_code: int, exit_status: Any) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is None:
            return
        session.process_state = ProcessState.STOPPED
        crashed = (
            exit_status == QProcess.ExitStatus.CrashExit
            or (int(exit_code) != 0 and not session.terminal_closed_received)
        )
        restart = session.restart_requested and not self._shutting_down
        host = session.host
        if crashed and not session.close_requested:
            session.process_state = ProcessState.ERROR
            session.last_error = f"Terminal process exited unexpectedly (code {exit_code})."
            self._set_state(session, "error", force=True)
            self.terminalError.emit(host, session.last_error)
        else:
            self._set_state(session, "closed", force=True)
        self._cleanup_session(session)
        if restart:
            QTimer.singleShot(0, lambda target=host: self.open(target))

    def _process_error(self, session_id: str, error: Any) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is None:
            return
        session.process_state = ProcessState.ERROR
        session.window_state = WindowState.ERROR
        session.last_error = f"NetworkTools Terminal process error: {error}"
        self._set_state(session, "error", force=True)
        self.terminalError.emit(session.host, session.last_error)
        if error == QProcess.ProcessError.FailedToStart:
            self._cleanup_session(session)

    def _ipc_connected(self, session_id: str) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is not None:
            session.ipc_state = IpcState.CONNECTED

    def _ipc_disconnected(self, session_id: str) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is not None:
            session.ipc_state = IpcState.DISCONNECTED
            self._set_state(session, session.ui_state)

    def _command_timed_out(self, session_id: str, _request_id: str, command: str) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is None:
            return
        if command == "window.close":
            self._stop_process(session)

    def _protocol_error(self, code: str, message: str) -> None:
        # Protocol errors are client-scoped until a validated session identity
        # exists; avoid attributing hostile input to an inventory device.
        _ = (code, message)

    def _close_fallback(self, session_id: str) -> None:
        session = self.sessions_by_id.get(session_id)
        if session is not None and session.process_state is not ProcessState.STOPPED:
            self._stop_process(session)

    def _simple_command(self, host: str, command: str, message: str) -> dict[str, Any]:
        session = self.session_for_device(host)
        if session is None:
            return self._result(False, "warning", f"No terminal is open for {host}.")
        request_id = self._ipc.send_command(session.session_id, command)
        if request_id is None:
            return self._result(False, "warning", "Terminal control channel is unavailable.")
        return self._result(True, "success", message, requestId=request_id)

    def _stop_process(self, session: TerminalSession, *, kill: bool = False) -> None:
        process = session.process
        if process is None or session.process_state is ProcessState.STOPPED:
            return
        method = getattr(process, "kill" if kill else "terminate", None)
        if callable(method):
            method()

    def _cleanup_session(self, session: TerminalSession) -> None:
        if self.sessions_by_id.get(session.session_id) is not session:
            return
        self.sessions_by_id.pop(session.session_id, None)
        if self.device_session.get(session.host) == session.session_id:
            self.device_session.pop(session.host, None)
        self._ipc.unregister_session(session.session_id)
        process = session.process
        if process is not None:
            delete_later = getattr(process, "deleteLater", None)
            if callable(delete_later):
                delete_later()
        session.process = None

    def _fail_open(self, host: str, message: str) -> dict[str, Any]:
        self._set_last_state(host, "error")
        self.terminalError.emit(host, message)
        return self._result(False, "error", message, state="error")

    def _set_state(self, session: TerminalSession, state: str, *, force: bool = False) -> None:
        previous = self._last_states.get(session.host)
        self._last_states[session.host] = state
        if force or previous != state:
            self.terminalStateChanged.emit(session.host, state)

    def _set_last_state(self, host: str, state: str) -> None:
        if not host:
            return
        previous = self._last_states.get(host)
        self._last_states[host] = state
        if previous != state:
            self.terminalStateChanged.emit(host, state)

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        parsed = ManagedTerminalManager._integer(value)
        return parsed if parsed is not None and parsed > 0 else None

    @staticmethod
    def _integer(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result(ok: bool, severity: str, message: str, **details: Any) -> dict[str, Any]:
        return {"ok": ok, "severity": severity, "message": message, **details}
