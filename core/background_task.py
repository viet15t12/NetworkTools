from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


ProgressCallback = Callable[[str], None]
TaskCallable = Callable[[ProgressCallback], Any]


class BackgroundTask(QObject):
    """Run a blocking callable on a worker thread and report Qt-safe signals."""

    taskStarted = pyqtSignal(str)
    taskProgress = pyqtSignal(str)
    taskFinished = pyqtSignal(str, bool, str, object)

    def __init__(self, task_key: str, start_message: str, callback: TaskCallable) -> None:
        super().__init__()
        self.task_key = task_key
        self._start_message = start_message
        self._callback = callback

    @pyqtSlot()
    def run(self) -> None:
        self.taskStarted.emit(self._start_message)
        try:
            result = self._callback(self.taskProgress.emit)
            ok, message = self._result_status(result)
        except Exception as exc:
            traceback.print_exc()
            result = {"ok": False, "message": str(exc)}
            ok = False
            message = str(exc) or "Task failed."

        self.taskFinished.emit(self.task_key, ok, message, result)

    def _result_status(self, result: Any) -> tuple[bool, str]:
        if isinstance(result, dict):
            ok = bool(result.get("ok", True))
            message = str(result.get("message") or ("Task completed." if ok else "Task failed."))
            return ok, message

        message = str(result).strip() if result is not None else "Task completed."
        return True, message or "Task completed."
