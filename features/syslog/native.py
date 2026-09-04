"""Qt bridge for the standalone C++ Syslog collector."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


APP_DIR = Path(__file__).resolve().parents[2]


class NativeSyslogCollector(QObject):
    """Translate JSON-line events from C++ into queued Qt signals."""

    ready = pyqtSignal(str)
    stopped = pyqtSignal()
    messageInserted = pyqtSignal("QVariant")
    collectorError = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._drain_stdout)
        self._process.readyReadStandardError.connect(self._drain_stderr)
        self._process.errorOccurred.connect(self._process_error)
        self._process.finished.connect(lambda *_: self.stopped.emit())
        self._stdout = bytearray()
        self._ready_message = ""
        self._last_error = ""
        self._dropped = 0

    @property
    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    @property
    def dropped(self) -> int:
        return self._dropped

    @staticmethod
    def executable_path() -> Path:
        override = os.environ.get("CAMS_SYSLOG_COLLECTOR", "").strip()
        if override:
            return Path(override).expanduser().resolve()
        return APP_DIR / "bin" / "cams-syslog-collector"

    def start(self, settings_path: Path, info_db: Path, device_db: Path) -> str:
        if self.is_running:
            return self._ready_message or "Native Syslog collector is running."
        executable = self.executable_path()
        if not executable.is_file():
            raise FileNotFoundError(
                f"Native Syslog collector is not built: {executable}. "
                "Run native/syslog_collector/build.sh."
            )
        self._stdout.clear()
        self._ready_message = ""
        self._last_error = ""
        self._dropped = 0
        self._process.setProgram(str(executable))
        self._process.setArguments([
            "--settings", str(Path(settings_path).resolve()),
            "--info-db", str(Path(info_db).resolve()),
            "--device-db", str(Path(device_db).resolve()),
        ])
        self._process.start()
        if not self._process.waitForStarted(2_000):
            raise RuntimeError(self._process.errorString() or "Could not start native Syslog collector")
        deadline_ms = 2_000
        while not self._ready_message and self.is_running and deadline_ms > 0:
            waited = min(100, deadline_ms)
            self._process.waitForReadyRead(waited)
            self._drain_stdout()
            deadline_ms -= waited
        if not self._ready_message:
            detail = self._last_error or "Native collector did not report readiness within 2 seconds."
            self.stop()
            raise RuntimeError(detail)
        return self._ready_message

    def stop(self) -> None:
        if not self.is_running:
            return
        self._process.terminate()
        if not self._process.waitForFinished(1_500):
            self._process.kill()
            self._process.waitForFinished(1_000)

    def _drain_stdout(self) -> None:
        self._stdout.extend(bytes(self._process.readAllStandardOutput()))
        while b"\n" in self._stdout:
            raw, _, remainder = self._stdout.partition(b"\n")
            self._stdout[:] = remainder
            if not raw.strip():
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.collectorError.emit(f"Invalid native Syslog event: {exc}")
                continue
            self._handle_event(event)

    def _handle_event(self, event: Any) -> None:
        if not isinstance(event, dict):
            return
        kind = str(event.get("type") or "")
        if kind == "ready":
            self._ready_message = str(event.get("message") or "Native Syslog collector is ready.")
            self.ready.emit(self._ready_message)
        elif kind == "message" and isinstance(event.get("row"), dict):
            self.messageInserted.emit(dict(event["row"]))
        elif kind == "dropped":
            self._dropped = max(0, int(event.get("count") or 0))
        elif kind == "error":
            self._last_error = str(event.get("message") or "Native Syslog collector error")
            self.collectorError.emit(self._last_error)

    def _drain_stderr(self) -> None:
        message = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if message:
            self._last_error = message
            self.collectorError.emit(message)

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        message = self._process.errorString().strip()
        if message:
            self._last_error = message
            self.collectorError.emit(message)


__all__ = ["NativeSyslogCollector"]
