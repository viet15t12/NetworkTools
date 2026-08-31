"""Qt event-loop NTTP/1 server for local managed terminal processes."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from .protocol import (
    COMMANDS,
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    NttpProtocolError,
    decode_line,
    encode_message,
    utc_timestamp,
)


@dataclass(slots=True)
class _PendingRequest:
    session_id: str
    command: str
    timer: QTimer


class NttpServer(QObject):
    """Receive bounded terminal events and send allowlisted window commands."""

    eventReceived = pyqtSignal(object)
    responseReceived = pyqtSignal(object)
    sessionConnected = pyqtSignal(str)
    sessionDisconnected = pyqtSignal(str)
    requestTimedOut = pyqtSignal(str, str, str)
    protocolError = pyqtSignal(str, str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        socket_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._configured_path = Path(socket_path) if socket_path is not None else None
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        self._buffers: dict[QLocalSocket, bytearray] = {}
        self._registered_sessions: set[str] = set()
        self._session_sockets: dict[str, QLocalSocket] = {}
        self._socket_sessions: dict[QLocalSocket, str] = {}
        self._pending: dict[str, _PendingRequest] = {}
        self._socket_path: Path | None = None

    @property
    def socket_path(self) -> str:
        """Return the active socket path, or the configured future path."""
        path = self._socket_path or self._configured_path
        return str(path) if path is not None else ""

    @property
    def is_listening(self) -> bool:
        """Return whether the local server currently accepts connections."""
        return self._server.isListening()

    def start(self) -> str:
        """Create a private runtime directory and begin listening."""
        if self._server.isListening():
            return self.socket_path
        path = self._configured_path or self._default_socket_path()
        self._prepare_parent(path.parent)
        self._remove_stale_socket(path)
        if not self._server.listen(str(path)):
            raise RuntimeError(
                f"Could not start the CAMS Terminal IPC server: "
                f"{self._server.errorString()}"
            )
        self._socket_path = path
        try:
            path.chmod(0o600)
        except OSError:
            self.stop()
            raise
        return str(path)

    def stop(self) -> None:
        """Close all clients, cancel requests, and remove the owned socket."""
        for pending in list(self._pending.values()):
            pending.timer.stop()
            pending.timer.deleteLater()
        self._pending.clear()
        for socket in list(self._buffers):
            socket.abort()
            socket.deleteLater()
        self._buffers.clear()
        self._session_sockets.clear()
        self._socket_sessions.clear()
        self._registered_sessions.clear()
        if self._server.isListening():
            self._server.close()
        path = self._socket_path
        self._socket_path = None
        if path is not None:
            QLocalServer.removeServer(str(path))

    def register_session(self, session_id: str) -> None:
        """Allow one manager-created session to announce itself."""
        self._registered_sessions.add(str(session_id))

    def unregister_session(self, session_id: str) -> None:
        """Forget a session and close any NTTP connection that claimed it."""
        session_id = str(session_id)
        self._registered_sessions.discard(session_id)
        socket = self._session_sockets.pop(session_id, None)
        if socket is not None:
            self._socket_sessions.pop(socket, None)
            socket.disconnectFromServer()
        for request_id, pending in list(self._pending.items()):
            if pending.session_id == session_id:
                pending.timer.stop()
                pending.timer.deleteLater()
                self._pending.pop(request_id, None)

    def is_connected(self, session_id: str) -> bool:
        """Return whether the session owns a connected local socket."""
        socket = self._session_sockets.get(str(session_id))
        return bool(
            socket is not None
            and socket.state() == QLocalSocket.LocalSocketState.ConnectedState
        )

    def send_command(
        self,
        session_id: str,
        command: str,
        data: dict[str, Any] | None = None,
        *,
        timeout_ms: int = 1500,
    ) -> str | None:
        """Queue an allowlisted command and return its request ID."""
        session_id = str(session_id)
        if command not in COMMANDS:
            raise NttpProtocolError("UNKNOWN_COMMAND", "Unsupported NTTP command.")
        socket = self._session_sockets.get(session_id)
        if socket is None or socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            return None
        request_id = f"req-{uuid4()}"
        encoded = encode_message(
            {
                "protocol": PROTOCOL_VERSION,
                "type": "command",
                "session_id": session_id,
                "request_id": request_id,
                "timestamp": utc_timestamp(),
                "command": command,
                "data": dict(data or {}),
            }
        )
        if socket.write(encoded) < 0:
            return None
        socket.flush()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda request=request_id: self._request_timed_out(request)
        )
        self._pending[request_id] = _PendingRequest(session_id, command, timer)
        timer.start(max(1, int(timeout_ms)))
        return request_id

    def _default_socket_path(self) -> Path:
        runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
        if not runtime:
            raise RuntimeError(
                "XDG_RUNTIME_DIR is required for CAMS Terminal IPC on Linux."
            )
        return Path(runtime) / "networktools" / "manager.sock"

    @staticmethod
    def _prepare_parent(parent: Path) -> None:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        details = parent.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise RuntimeError("The terminal IPC runtime path is not a safe directory.")
        if hasattr(os, "getuid") and details.st_uid != os.getuid():
            raise RuntimeError("The terminal IPC runtime directory is not user-owned.")
        parent.chmod(0o700)

    @staticmethod
    def _remove_stale_socket(path: Path) -> None:
        try:
            details = path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(details.st_mode):
            raise RuntimeError("The terminal IPC path exists and is not a socket.")
        if hasattr(os, "getuid") and details.st_uid != os.getuid():
            raise RuntimeError("The terminal IPC socket is not user-owned.")
        if not QLocalServer.removeServer(str(path)):
            raise RuntimeError("The stale terminal IPC socket could not be removed.")

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                return
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda client=socket: self._read_socket(client))
            socket.disconnected.connect(
                lambda client=socket: self._socket_disconnected(client)
            )

    def _read_socket(self, socket: QLocalSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > MAX_MESSAGE_BYTES and b"\n" not in buffer:
            self._reject_socket(socket, "MESSAGE_TOO_LARGE", "NTTP message exceeds 64 KiB.")
            return
        while b"\n" in buffer:
            raw_line, _separator, remainder = buffer.partition(b"\n")
            buffer[:] = remainder
            if not raw_line.strip():
                continue
            try:
                message = decode_line(raw_line)
                self._handle_message(socket, message)
            except NttpProtocolError as exc:
                self._reject_socket(socket, exc.code, str(exc))
                return
        if len(buffer) > MAX_MESSAGE_BYTES:
            self._reject_socket(socket, "MESSAGE_TOO_LARGE", "NTTP message exceeds 64 KiB.")

    def _handle_message(self, socket: QLocalSocket, message: dict[str, Any]) -> None:
        session_id = message["session_id"]
        if session_id not in self._registered_sessions:
            raise NttpProtocolError("UNKNOWN_SESSION", "NTTP session is not registered.")
        claimed = self._socket_sessions.get(socket)
        if claimed is not None and claimed != session_id:
            raise NttpProtocolError("SESSION_CHANGED", "A socket cannot change NTTP session.")
        current = self._session_sockets.get(session_id)
        if current is not None and current is not socket:
            raise NttpProtocolError("DUPLICATE_SESSION", "NTTP session already has a client.")
        if claimed is None:
            self._socket_sessions[socket] = session_id
            self._session_sockets[session_id] = socket
            self.sessionConnected.emit(session_id)

        if message["type"] == "event":
            self.eventReceived.emit(message)
            return
        request_id = message["request_id"]
        pending = self._pending.pop(request_id, None)
        if pending is None or pending.session_id != session_id:
            raise NttpProtocolError("UNKNOWN_REQUEST", "NTTP response request is unknown.")
        pending.timer.stop()
        pending.timer.deleteLater()
        self.responseReceived.emit(message)

    def _request_timed_out(self, request_id: str) -> None:
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return
        pending.timer.deleteLater()
        self.requestTimedOut.emit(pending.session_id, request_id, pending.command)

    def _reject_socket(self, socket: QLocalSocket, code: str, message: str) -> None:
        self.protocolError.emit(code, message)
        socket.abort()

    def _socket_disconnected(self, socket: QLocalSocket) -> None:
        self._buffers.pop(socket, None)
        session_id = self._socket_sessions.pop(socket, None)
        if session_id is not None and self._session_sockets.get(session_id) is socket:
            self._session_sockets.pop(session_id, None)
            self.sessionDisconnected.emit(session_id)
        socket.deleteLater()
