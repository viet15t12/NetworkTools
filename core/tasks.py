"""Single Qt thread coordinator shared by all core QML facades."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QThread

from .background_task import BackgroundTask, TaskCallable

TaskEventCallback = Callable[..., None]


class AsyncTaskCoordinator(QObject):
    """Own worker/thread lifecycles and reject duplicate task keys."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize strong references retained until each worker completes."""
        super().__init__(parent)
        self._tasks: dict[str, dict[str, Any]] = {}

    def is_running(self, task_key: str) -> bool:
        """Return whether task_key currently owns a live worker thread."""
        return task_key in self._tasks

    def start(
        self,
        task_key: str,
        start_message: str,
        callback: TaskCallable,
        *,
        on_started: TaskEventCallback,
        on_progress: TaskEventCallback,
        on_finished: TaskEventCallback,
    ) -> bool:
        """Run callback on one QThread and relay its events to a facade."""
        if self.is_running(task_key):
            return False
        thread = QThread(self)
        worker = BackgroundTask(task_key, start_message, callback)
        worker.moveToThread(thread)
        self._tasks[task_key] = {"thread": thread, "worker": worker}
        thread.started.connect(worker.run)
        worker.taskStarted.connect(on_started)
        worker.taskProgress.connect(on_progress)
        worker.taskFinished.connect(on_finished)
        worker.taskFinished.connect(self._cleanup_task)
        worker.taskFinished.connect(lambda *_args, current=thread: current.quit())
        worker.taskFinished.connect(lambda *_args, current=worker: current.deleteLater())
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def shutdown(self) -> None:
        """Request active threads to exit during application shutdown."""
        for entry in tuple(self._tasks.values()):
            entry["thread"].requestInterruption()
            entry["thread"].quit()

    def _cleanup_task(self, task_key: str, *_args: object) -> None:
        """Release coordinator references after a worker reports completion."""
        self._tasks.pop(task_key, None)


__all__ = ["AsyncTaskCoordinator", "BackgroundTask"]
