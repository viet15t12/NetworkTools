from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    completed = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)


class OperationWorker(QRunnable):
    def __init__(self, operation: str, function: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.function = function
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:
            self.signals.failed.emit(self.operation, str(exc))
        else:
            self.signals.completed.emit(self.operation, result)
