"""Background owner of one interactive Netmiko channel."""

from __future__ import annotations

import queue
import threading
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from .stream import TerminalOutputNormalizer


class TerminalStreamWorker(QThread):
    """Read and write one device channel while the registry lock is held."""

    outputReady = pyqtSignal(str)
    stateChanged = pyqtSignal(str, str)

    def __init__(self, host: str, session_registry: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.host = (host or "").strip()
        self._session_registry = session_registry
        self._input: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()

    def send(self, text: str) -> None:
        """Queue terminal input; only this worker writes to the channel."""
        if text and not self._stop_event.is_set():
            self._input.put(str(text))

    def stop(self) -> None:
        """Request a safe stop at the next channel polling boundary."""
        self._stop_event.set()

    def run(self) -> None:
        self.stateChanged.emit("connecting", f"Connecting to {self.host}...")
        result = self._session_registry.execute(
            self.host,
            self._run_interactive_loop,
            ensure_open=True,
        )
        if self._stop_event.is_set():
            self.stateChanged.emit("closed", f"Terminal closed for {self.host}.")
        elif not bool(result.get("ok")):
            message = str(result.get("message") or f"Terminal failed for {self.host}.")
            self.outputReady.emit(f"\r\n[CAMS] {message}\r\n")
            self.stateChanged.emit("error", message)
        else:
            self.stateChanged.emit("closed", f"Terminal session ended for {self.host}.")

    def _run_interactive_loop(self, connector: Any) -> None:
        connection = getattr(connector, "connection", None)
        if connection is None:
            raise RuntimeError("Active session has no Netmiko connection.")
        read_channel = getattr(connection, "read_channel", None)
        write_channel = getattr(connection, "write_channel", None)
        if not callable(read_channel) or not callable(write_channel):
            raise RuntimeError("The active transport does not support interactive CLI.")

        self._prepare_exec_prompt(connection)
        normalizer = TerminalOutputNormalizer()
        raw_linefeeds_supported = hasattr(connection, "disable_lf_normalization")
        previous_linefeed_mode = getattr(
            connection, "disable_lf_normalization", False
        )
        if raw_linefeeds_supported:
            # pyte needs the original CR/LF cursor semantics, not Netmiko's
            # command-oriented LF normalization.
            connection.disable_lf_normalization = True

        try:
            self.stateChanged.emit(
                "connected", f"Interactive CLI connected to {self.host}."
            )
            # Ask IOS to repaint its prompt after stale command output is drained.
            write_channel("\r")
            while not self._stop_event.is_set():
                self._flush_input(write_channel)
                output = read_channel()
                if output:
                    cleaned = normalizer.feed(str(output))
                    if cleaned:
                        self.outputReady.emit(cleaned)
                self._stop_event.wait(0.02)
            remainder = normalizer.flush()
            if remainder:
                self.outputReady.emit(remainder)
        finally:
            if raw_linefeeds_supported:
                connection.disable_lf_normalization = previous_linefeed_mode

    @staticmethod
    def _prepare_exec_prompt(connection: Any) -> None:
        """Leave configuration mode and remove buffered output before repaint."""
        check_enable = getattr(connection, "check_enable_mode", None)
        if callable(check_enable) and not check_enable():
            connection.enable()
        check_config = getattr(connection, "check_config_mode", None)
        if callable(check_config) and check_config():
            connection.exit_config_mode()
        clear_buffer = getattr(connection, "clear_buffer", None)
        if callable(clear_buffer):
            clear_buffer()

    def _flush_input(self, write_channel: Any) -> None:
        chunks: list[str] = []
        while True:
            try:
                chunks.append(self._input.get_nowait())
            except queue.Empty:
                break
        if chunks:
            write_channel("".join(chunks))
