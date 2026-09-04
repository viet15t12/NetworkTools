"""Asynchronous bridge between the Settings UI and the Linux updater."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtProperty, pyqtSignal, pyqtSlot

from infrastructure.database.paths import APP_DIR


class UpdateManager(QObject):
    """Run update.sh without blocking the Qt event loop."""

    stateChanged = pyqtSignal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        app_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_dir = Path(app_dir or APP_DIR).resolve()
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._drain_output)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_finished)
        self._output = bytearray()
        self._busy = False
        self._restart_required = False
        self._status_message = "Ready to check for updates."
        self._status_severity = "info"
        self._result_status = ""
        self._current_commit = self._read_release_commit()
        self._latest_commit = ""

    @property
    def script_path(self) -> Path:
        return self._app_dir / "update.sh"

    def _read_release_commit(self) -> str:
        metadata = self._app_dir / ".cams-release"
        try:
            first_line = metadata.read_text(encoding="utf-8").splitlines()[0].strip()
            if first_line:
                return first_line
        except (OSError, IndexError):
            pass
        try:
            completed = subprocess.run(
                ["git", "-C", str(self._app_dir), "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if completed.returncode == 0:
                return completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return "unknown"

    def _application_version(self) -> str:
        try:
            with (self._app_dir / "pyproject.toml").open("rb") as stream:
                return str(tomllib.load(stream)["project"]["version"])
        except (KeyError, OSError, tomllib.TOMLDecodeError):
            return "unknown"

    @pyqtProperty(bool, notify=stateChanged)
    def available(self) -> bool:
        return sys.platform.startswith("linux") and self.script_path.is_file()

    @pyqtProperty(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @pyqtProperty(bool, notify=stateChanged)
    def restartRequired(self) -> bool:
        return self._restart_required

    @pyqtProperty(str, notify=stateChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @pyqtProperty(str, notify=stateChanged)
    def statusSeverity(self) -> str:
        return self._status_severity

    @pyqtProperty(str, notify=stateChanged)
    def currentVersion(self) -> str:
        commit = (
            self._current_commit[:12]
            if self._current_commit != "unknown"
            else "unknown"
        )
        return f"{self._application_version()} ({commit})"

    @pyqtProperty(str, notify=stateChanged)
    def latestVersion(self) -> str:
        return self._latest_commit[:12]

    @pyqtSlot(result=bool)
    def checkAndUpdate(self) -> bool:
        if self._busy:
            return False
        if not self.available:
            self._status_message = "Automatic updates are available on Linux installations only."
            self._status_severity = "warning"
            self.stateChanged.emit()
            return False

        self._output.clear()
        self._result_status = ""
        self._busy = True
        self._status_message = "Checking for CAMS updates..."
        self._status_severity = "info"
        self.stateChanged.emit()
        self._process.setWorkingDirectory(str(self._app_dir))
        self._process.start("/bin/sh", [str(self.script_path), "--update"])
        return True

    def _drain_output(self) -> None:
        self._output.extend(bytes(self._process.readAllStandardOutput()))

    def _parse_output(self) -> None:
        text = self._output.decode("utf-8", errors="replace")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("CAMS_UPDATE_STATUS="):
                self._result_status = line.partition("=")[2]
            elif line.startswith("CAMS_UPDATE_CURRENT="):
                self._current_commit = line.partition("=")[2] or self._current_commit
            elif line.startswith("CAMS_UPDATE_LATEST="):
                self._latest_commit = line.partition("=")[2]

    @pyqtSlot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._drain_output()
        self._parse_output()
        self._busy = False
        if exit_code != 0:
            output = self._output.decode("utf-8", errors="replace")
            errors = [
                line.removeprefix("ERROR:").strip()
                for line in output.splitlines()
                if "ERROR:" in line
            ]
            self._status_message = (
                errors[-1]
                if errors
                else "CAMS update failed. Check the network connection and try again."
            )
            self._status_severity = "error"
        elif self._result_status == "updated":
            self._current_commit = self._latest_commit or self._current_commit
            self._restart_required = True
            self._status_message = (
                "CAMS was updated successfully. Restart the app to use the new version."
            )
            self._status_severity = "success"
        elif self._result_status == "current":
            self._status_message = "CAMS is already up to date."
            self._status_severity = "success"
        else:
            self._status_message = "The update check finished without a recognizable result."
            self._status_severity = "warning"
        self.stateChanged.emit()

    @pyqtSlot(QProcess.ProcessError)
    def _on_process_error(self, _error: QProcess.ProcessError) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._busy = False
        self._status_message = self._process.errorString() or "Could not start the CAMS updater."
        self._status_severity = "error"
        self.stateChanged.emit()

    def shutdown(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()
        if not self._process.waitForFinished(1_000):
            self._process.kill()
            self._process.waitForFinished(1_000)


__all__ = ["UpdateManager"]
