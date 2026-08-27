"""Lifecycle manager for independent internal terminal windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject

from .window import InternalTerminalWindow
from .worker import TerminalStreamWorker


@dataclass(slots=True)
class _ManagedTerminal:
    window: InternalTerminalWindow
    worker: TerminalStreamWorker | None = None
    closing: bool = False
    restart_after_stop: bool = False


class InternalTerminalManager(QObject):
    """Own at most one interactive window and worker for each device host."""

    def __init__(
        self,
        session_registry: Any,
        parent: QObject | None = None,
        *,
        device_loader: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_registry = session_registry
        self._device_loader = device_loader
        self._terminals: dict[str, _ManagedTerminal] = {}

    def open(self, host: str) -> dict[str, Any]:
        """Show or focus the app-managed terminal for one inventory host."""
        host = (host or "").strip()
        if not host:
            return {
                "ok": False,
                "severity": "warning",
                "message": "Select a device before opening CLI.",
            }
        preflight = self._preflight(host)
        if not preflight["ok"]:
            return preflight

        managed = self._terminals.get(host)
        if managed is None:
            window = InternalTerminalWindow(host)
            managed = _ManagedTerminal(window=window)
            self._terminals[host] = managed
            window.inputGenerated.connect(
                lambda text, target=host: self.send(target, text)
            )
            window.closeRequested.connect(
                lambda target=host: self.close(target)
            )
            window.reconnectRequested.connect(
                lambda target=host: self.reconnect(target)
            )
            self._start_worker(host, managed)
        else:
            was_closing = managed.closing
            managed.closing = False
            if managed.worker is None or not managed.worker.isRunning():
                self._start_worker(host, managed)
            elif was_closing:
                # The stopped worker must release the host lock before a new
                # reader can safely own the same Netmiko channel.
                managed.restart_after_stop = True

        managed.window.show()
        managed.window.raise_()
        managed.window.activateWindow()
        return {
            "ok": True,
            "severity": "success",
            "message": f"NetworkTools CLI opened for {host}.",
        }

    def send(self, host: str, text: str) -> None:
        """Forward input to the worker that owns the selected host channel."""
        managed = self._terminals.get((host or "").strip())
        if managed is not None and managed.worker is not None:
            managed.worker.send(text)

    def reconnect(self, host: str) -> None:
        """Restart a stopped worker while preserving its terminal window."""
        managed = self._terminals.get((host or "").strip())
        if managed is None:
            self.open(host)
            return
        preflight = self._preflight(host)
        if not preflight["ok"]:
            managed.window.set_connection_state(
                str(preflight.get("severity") or "error"),
                str(preflight.get("message") or "CLI preflight failed."),
            )
            return
        if managed.worker is not None and managed.worker.isRunning():
            if managed.closing:
                managed.closing = False
                managed.restart_after_stop = True
                managed.window.set_connection_state(
                    "connecting", f"Reconnecting terminal for {host}..."
                )
                return
            managed.window.set_connection_state(
                "connected", f"Interactive CLI is already active for {host}."
            )
            return
        managed.closing = False
        self._start_worker(host, managed)

    def close(self, host: str) -> None:
        """Stop terminal channel polling but keep the reusable registry session."""
        host = (host or "").strip()
        managed = self._terminals.get(host)
        if managed is None:
            return
        managed.closing = True
        managed.restart_after_stop = False
        managed.window.hide()
        if managed.worker is None or not managed.worker.isRunning():
            self._dispose(host, managed)
            return
        managed.worker.stop()

    def shutdown(self, timeout_ms: int = 1500) -> None:
        """Stop every terminal before the shared session registry disconnects."""
        terminals = list(self._terminals.items())
        for _host, managed in terminals:
            managed.closing = True
            managed.restart_after_stop = False
            managed.window.hide()
            if managed.worker is not None:
                managed.worker.stop()
        for host, managed in terminals:
            worker = managed.worker
            if worker is not None and worker.isRunning():
                worker.wait(max(0, int(timeout_ms)))
            self._dispose(host, managed)

    def _start_worker(self, host: str, managed: _ManagedTerminal) -> None:
        worker = TerminalStreamWorker(host, self._session_registry, self)
        managed.worker = worker
        worker.outputReady.connect(managed.window.enqueue_output)
        worker.stateChanged.connect(managed.window.set_connection_state)
        worker.finished.connect(
            lambda target=host, expected=worker: self._worker_finished(
                target, expected
            )
        )
        worker.start()

    def _preflight(self, host: str) -> dict[str, Any]:
        """Reject inventory modes that intentionally prohibit real CLI access."""
        if self._device_loader is None:
            return {"ok": True}
        device = self._device_loader(host)
        if device is None:
            return {
                "ok": False,
                "severity": "error",
                "message": f"Device {host} was not found.",
            }
        if int(device.get("dev") or 0) == 1:
            return {
                "ok": False,
                "severity": "warning",
                "message": (
                    f"{host} is in development mode, which disables real SSH/Telnet. "
                    "Switch to Live Connection, then Connect before opening CLI."
                ),
            }
        method = str(device.get("method") or "").strip().lower()
        if method not in {"ssh", "telnet"}:
            return {
                "ok": False,
                "severity": "warning",
                "message": f"Interactive CLI does not support method {method or 'unknown'}.",
            }
        return {"ok": True}

    def _worker_finished(self, host: str, worker: TerminalStreamWorker) -> None:
        managed = self._terminals.get(host)
        if managed is None or managed.worker is not worker:
            worker.deleteLater()
            return
        managed.worker = None
        worker.deleteLater()
        if managed.closing:
            self._dispose(host, managed)
        elif managed.restart_after_stop:
            managed.restart_after_stop = False
            self._start_worker(host, managed)

    def _dispose(self, host: str, managed: _ManagedTerminal) -> None:
        if self._terminals.get(host) is not managed:
            return
        self._terminals.pop(host, None)
        managed.window.deleteLater()
