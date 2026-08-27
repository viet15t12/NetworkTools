"""Thread-safe owner for reusable device sessions."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .connector import ConnectorFactory, create_connector
from .session_entry import SessionEntry


class DeviceSessionRegistry:
    def __init__(
        self,
        device_loader: Callable[[str], dict[str, Any] | None],
        *,
        connector_factory: ConnectorFactory = create_connector,
    ) -> None:
        self._device_loader = device_loader
        self._connector_factory = connector_factory
        self._lock = threading.RLock()
        self._sessions: dict[str, SessionEntry | Any] = {}

    def _entry(self, host: str) -> SessionEntry:
        with self._lock:
            current = self._sessions.get(host)
            if isinstance(current, SessionEntry):
                return current
            entry = SessionEntry(host=host, connector=current)
            if current is not None and self._is_alive(current):
                entry.state = "connected"
                entry.opened_at = time.time()
                entry.touch()
            self._sessions[host] = entry
            return entry

    @staticmethod
    def _is_alive(connector: Any) -> bool:
        if connector is None or not bool(getattr(connector, "connected", False)):
            return False
        connection = getattr(connector, "connection", None)
        if connection is None:
            return False
        probe = getattr(connection, "is_alive", None)
        try:
            return bool(probe()) if callable(probe) else True
        except Exception:
            return False

    @staticmethod
    def _disconnect(connector: Any) -> None:
        try:
            connector.disconnect()
        except Exception:
            pass

    @staticmethod
    def _prepare(connector: Any) -> None:
        connection = getattr(connector, "connection", None)
        if connection is None:
            raise RuntimeError("Network connection was not created")
        if callable(getattr(connection, "check_enable_mode", None)) and not connection.check_enable_mode():
            connection.enable()
        if callable(getattr(connection, "check_config_mode", None)) and connection.check_config_mode():
            connection.exit_config_mode()

    def open(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        if not host:
            return {"ok": False, "severity": "warning", "message": "Open session failed: host is empty."}
        entry = self._entry(host)
        with entry.operation_lock:
            if self._is_alive(entry.connector):
                entry.state = "connected"
                entry.touch()
                return {"ok": True, "severity": "info", "message": f"Session for {host} is already open."}
            device = self._device_loader(host)
            if device is None:
                entry.state = "error"
                entry.last_error = f"Device {host} was not found."
                return {"ok": False, "severity": "error", "message": entry.last_error}
            if int(device.get("dev") or 0) == 1:
                entry.state = "closed"
                return {
                    "ok": False,
                    "severity": "warning",
                    "message": (
                        f"{host} is in development mode, so real network access is disabled. "
                        "Switch to Live Connection, then Connect before opening CLI."
                    ),
                }
            if device.get("method") not in {"ssh", "telnet"}:
                entry.state = "closed"
                return {
                    "ok": False,
                    "severity": "warning",
                    "message": (
                        f"Interactive CLI is unavailable for {host}: "
                        f"unsupported method {device.get('method') or 'unknown'}."
                    ),
                }
            connector = None
            entry.state = "opening"
            entry.last_error = ""
            try:
                connector = self._connector_factory(device)
                if not connector.connect():
                    reason = str(getattr(connector, "last_error", "login failed"))
                    entry.state = "error"
                    entry.last_error = reason
                    self._disconnect(connector)
                    return {"ok": False, "severity": "error", "message": f"Open session failed for {host}: {reason}."}
                self._prepare(connector)
                previous = entry.connector
                entry.connector = connector
                entry.state = "connected"
                entry.opened_at = time.time()
                entry.touch()
                entry.generation += 1
                if previous is not None and previous is not connector:
                    self._disconnect(previous)
                return {"ok": True, "severity": "success", "message": f"Session opened for {host}."}
            except Exception as exc:
                if connector is not None:
                    self._disconnect(connector)
                entry.state = "error"
                entry.last_error = str(exc)
                return {"ok": False, "severity": "error", "message": f"Open session failed for {host}: {exc}"}

    def close(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        with self._lock:
            raw = self._sessions.get(host)
        if raw is None:
            return {"ok": True, "severity": "info", "message": f"Session closed for {host}."}
        entry = raw if isinstance(raw, SessionEntry) else self._entry(host)
        with entry.operation_lock:
            connector = entry.connector
            entry.state = "closing"
            entry.connector = None
            if connector is not None:
                self._disconnect(connector)
            entry.state = "closed"
            entry.touch()
        with self._lock:
            self._sessions.pop(host, None)
        return {"ok": True, "severity": "success" if connector else "info", "message": f"Session closed for {host}."}

    def close_all(self, timeout: float | None = 1.0) -> None:
        """Close sessions concurrently, optionally waiting for every disconnect."""
        with self._lock:
            entries = list(self._sessions.values())
            self._sessions.clear()
        sessions = [
            entry.connector if isinstance(entry, SessionEntry) else entry
            for entry in entries
        ]
        workers = [
            threading.Thread(
                target=self._disconnect,
                args=(connector,),
                name=f"device-disconnect-{index}",
                daemon=True,
            )
            for index, connector in enumerate(sessions, start=1)
        ]
        for worker in workers:
            worker.start()
        if timeout is None:
            for worker in workers:
                worker.join()
            return
        deadline = time.monotonic() + max(0.0, timeout)
        for worker in workers:
            worker.join(max(0.0, deadline - time.monotonic()))

    def get_connector(self, host: str) -> Any | None:
        with self._lock:
            raw = self._sessions.get((host or "").strip())
            connector = raw.connector if isinstance(raw, SessionEntry) else raw
            if self._is_alive(connector):
                return connector
        return None

    def has_session(self, host: str) -> bool:
        return self.get_connector(host) is not None

    def get_state(self, host: str) -> str:
        with self._lock:
            raw = self._sessions.get((host or "").strip())
            if isinstance(raw, SessionEntry):
                return raw.state
            return "connected" if self._is_alive(raw) else "closed"

    def snapshot(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        with self._lock:
            raw = self._sessions.get(host)
            if isinstance(raw, SessionEntry):
                return raw.snapshot()
        return SessionEntry(host=host, state=self.get_state(host)).snapshot()

    def execute(
        self,
        host: str,
        operation: Callable[[Any], Any],
        *,
        ensure_open: bool = True,
        lock_timeout: float | None = None,
    ) -> dict[str, Any]:
        """Serialize CLI access for host and optionally create its session."""
        host = (host or "").strip()
        if not host:
            return {"ok": False, "severity": "warning", "message": "Operation failed: host is empty."}
        # Preserve compatibility with callers/tests that provide an already
        # established connector through the former get_connector() contract.
        existing = self.get_connector(host)
        entry = self._entry(host)
        acquired = (
            entry.operation_lock.acquire()
            if lock_timeout is None
            else entry.operation_lock.acquire(timeout=max(0.0, float(lock_timeout)))
        )
        if not acquired:
            return {
                "ok": False,
                "severity": "warning",
                "code": "session_busy",
                "message": (
                    f"Device session for {host} is busy with another operation. "
                    "Wait for its background synchronization to finish, then try Push again."
                ),
            }
        try:
            if existing is not None and entry.connector is not existing:
                previous = entry.connector
                entry.connector = existing
                entry.state = "connected"
                entry.opened_at = time.time()
                entry.touch()
                entry.generation += 1
                if previous is not None:
                    self._disconnect(previous)
            if not self._is_alive(entry.connector) and existing is None:
                entry.state = "stale" if entry.connector is not None else "closed"
                if not ensure_open:
                    return {"ok": False, "severity": "error", "message": f"No active session for {host}."}
                opened = self.open(host)
                if not opened.get("ok"):
                    return opened
                # A successful open must always produce a live connector before
                # user code is invoked. This prevents a misleading operation
                # failure against None when a connection policy rejects a host.
                if not self._is_alive(entry.connector):
                    entry.state = "error"
                    entry.last_error = f"Session for {host} opened without a live connector."
                    return {
                        "ok": False,
                        "severity": "error",
                        "message": entry.last_error,
                    }
            generation = entry.generation
            try:
                # Normalize the reusable session before every operation so a
                # prior interactive command cannot leave a stale config prompt.
                if getattr(entry.connector, "connection", None) is not None:
                    self._prepare(entry.connector)
                value = operation(entry.connector)
                if generation == entry.generation:
                    entry.state = "connected"
                    entry.touch()
                return {
                    "ok": True, "severity": "success",
                    "message": f"Operation completed for {host}.", "value": value,
                    "generation": generation,
                }
            except Exception as exc:
                if generation == entry.generation:
                    entry.last_error = str(exc)
                    entry.state = "stale" if not self._is_alive(entry.connector) else "connected"
                return {
                    "ok": False, "severity": "error",
                    "message": f"Operation failed for {host}: {exc}",
                    "generation": generation,
                }
        finally:
            entry.operation_lock.release()
