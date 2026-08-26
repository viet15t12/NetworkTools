"""Non-blocking QML bridge for serialized workspace saves and snapshots."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QFileSystemWatcher,
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)

from infrastructure.workspace import (
    RollbackResult,
    SaveResult,
    WorkspaceConflictError,
    WorkspaceService,
    WorkspaceSession,
)

from .welcome import WelcomeController


@dataclass(frozen=True, slots=True)
class _OperationRequest:
    kind: str
    reason: str
    force: bool = True
    create_snapshot: bool = False
    snapshot_label: str = ""
    snapshot_reason: str = "manual"
    snapshot_pinned: bool = False
    snapshot_id: str = ""
    generation: int = 0


class _WorkerSignals(QObject):
    finished = pyqtSignal(object, object, object, object, object)


class _WorkspaceOperation(QRunnable):
    def __init__(
        self,
        service: WorkspaceService,
        session: WorkspaceSession,
        request: _OperationRequest,
        session_lease: object,
        operation_token: object,
        workspace_close_preparer: Callable[[], None] | None,
    ) -> None:
        super().__init__()
        self.service = service
        self.session = session
        self.request = request
        self.session_lease = session_lease
        self.operation_token = operation_token
        self.workspace_close_preparer = workspace_close_preparer
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        result: SaveResult | RollbackResult | None = None
        error: Exception | None = None
        try:
            if (
                self.request.kind == "close"
                and self.workspace_close_preparer is not None
            ):
                # Closing a workspace is a strict transaction: device sessions
                # must be gone before the extracted databases are packaged.
                self.workspace_close_preparer()
            if self.request.kind == "rollback":
                result = self.service.rollback_project(
                    self.session,
                    self.request.snapshot_id,
                    source_generation=self.request.generation,
                    _session_lease=True,
                )
            else:
                result = self.service.save_project(
                    self.session,
                    reason=self.request.reason,
                    force=self.request.force,
                    create_snapshot=self.request.create_snapshot,
                    snapshot_label=self.request.snapshot_label,
                    snapshot_reason=self.request.snapshot_reason,
                    source_generation=self.request.generation,
                    snapshot_pinned=self.request.snapshot_pinned,
                    _session_lease=True,
                )
        except Exception as exc:  # relayed to the GUI thread as data
            error = exc
        finally:
            try:
                self.session_lease.__exit__(None, None, None)  # type: ignore[attr-defined]
            except Exception as cleanup_error:
                if error is None:
                    error = cleanup_error
        self.signals.finished.emit(
            self.operation_token, self.session, self.request, result, error
        )


class WorkspaceSaveController(QObject):
    """Own one background writer, a 3-minute timer, and QML save state."""

    stateChanged = pyqtSignal()
    snapshotsChanged = pyqtSignal()
    notificationRequested = pyqtSignal(str, str)
    saveCompleted = pyqtSignal(str)
    saveFailed = pyqtSignal(str)
    workspaceCloseCompleted = pyqtSignal()

    def __init__(
        self,
        welcome_controller: WelcomeController,
        parent: QObject | None = None,
        *,
        workspace_service: WorkspaceService | None = None,
        autosave_interval_ms: int = 3 * 60 * 1000,
        autosave_idle_delay_ms: int = 5_000,
        workspace_close_preparer: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._welcome = welcome_controller
        self._service = workspace_service or welcome_controller.workspace_service
        self._workspace_close_preparer = workspace_close_preparer
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._workspace_file_changed)
        self._watcher.directoryChanged.connect(self._workspace_file_changed)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(max(1, autosave_interval_ms))
        self._autosave_timer.timeout.connect(self.requestAutoSave)
        self._idle_autosave_timer = QTimer(self)
        self._idle_autosave_timer.setSingleShot(True)
        self._idle_autosave_timer.setInterval(max(1, autosave_idle_delay_ms))
        self._idle_autosave_timer.timeout.connect(self.requestAutoSave)
        self._busy = False
        self._state = "no_workspace"
        self._status_text = "No workspace"
        self._last_saved_at = ""
        self._generation = 0
        self._saved_generation = 0
        self._active_request: _OperationRequest | None = None
        self._pending_request: _OperationRequest | None = None
        # QThreadPool owns the C++ QRunnable, but PyQt does not guarantee that
        # its Python wrapper (and childless signal object) survives until a
        # queued GUI-thread signal is delivered. Keep explicit ownership.
        self._workers: dict[object, _WorkspaceOperation] = {}
        self._snapshots: list[dict[str, Any]] = []
        self._shutting_down = False
        self._welcome.activeWorkspaceChanged.connect(self._workspace_changed)
        self._workspace_changed()

    @pyqtProperty(bool, notify=stateChanged)
    def hasWorkspace(self) -> bool:
        return self._welcome.active_session() is not None

    @pyqtProperty(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @pyqtProperty(bool, notify=stateChanged)
    def dirty(self) -> bool:
        return self._generation > self._saved_generation

    @pyqtProperty(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @pyqtProperty(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status_text

    @pyqtProperty(str, notify=stateChanged)
    def lastSavedAt(self) -> str:
        return self._last_saved_at

    @pyqtProperty("QVariantList", notify=snapshotsChanged)
    def snapshots(self) -> list[dict[str, Any]]:
        return [dict(snapshot) for snapshot in self._snapshots]

    @pyqtSlot()
    def markDirty(self) -> None:
        if not self.hasWorkspace:
            return
        self._generation += 1
        # Restarting a single-shot timer coalesces a burst of SQLite/QML file
        # notifications into one background package write after activity has
        # settled.  The periodic timer remains a safety net for changes below
        # directories QFileSystemWatcher cannot observe recursively.
        self._idle_autosave_timer.start()
        if not self._busy:
            self._set_state("unsaved", "Unsaved changes")

    @pyqtSlot(result=bool)
    def requestManualSave(self) -> bool:
        return self._enqueue(
            _OperationRequest(
                kind="save",
                reason="manual",
                force=True,
                generation=self._generation,
            )
        )

    @pyqtSlot(result=bool)
    def requestAutoSave(self) -> bool:
        return self._enqueue(
            _OperationRequest(
                kind="save",
                reason="automatic",
                force=False,
                create_snapshot=True,
                snapshot_reason="automatic",
                generation=self._generation,
            )
        )

    @pyqtSlot(result=bool)
    def requestCloseWorkspace(self) -> bool:
        """Save pending edits, then release the extracted workspace."""

        return self._enqueue(
            _OperationRequest(
                kind="close",
                reason="close",
                # Always rebuild and verify the .ntp package on an explicit
                # Close Workspace, even when no file watcher marked it dirty.
                force=True,
                generation=self._generation,
            )
        )

    @pyqtSlot(str, result=bool)
    def createSnapshot(self, label: str = "") -> bool:
        return self._enqueue(
            _OperationRequest(
                kind="snapshot",
                reason="snapshot",
                force=True,
                create_snapshot=True,
                snapshot_label=(label or "").strip(),
                snapshot_reason="manual",
                generation=self._generation,
            )
        )

    @pyqtSlot(str, result=bool)
    def rollbackSnapshot(self, snapshot_id: str) -> bool:
        snapshot_id = (snapshot_id or "").strip()
        if not snapshot_id:
            return False
        return self._enqueue(
            _OperationRequest(
                kind="rollback",
                reason="rollback",
                snapshot_id=snapshot_id,
                generation=self._generation,
            )
        )

    def _enqueue(self, request: _OperationRequest) -> bool:
        if self._shutting_down or not self.hasWorkspace:
            return False
        if self._busy:
            self._pending_request = self._merge_pending(
                self._pending_request, request
            )
            return True
        return self._start(request)

    def _start(self, request: _OperationRequest) -> bool:
        session = self._welcome.active_session()
        if session is None or session.is_closed:
            return False
        request = replace(request, generation=self._generation)
        session_lease = session.operation()
        try:
            session_lease.__enter__()
        except RuntimeError:
            return False
        operation_token = object()
        worker = _WorkspaceOperation(
            self._service,
            session,
            request,
            session_lease,
            operation_token,
            self._workspace_close_preparer,
        )
        worker.signals.finished.connect(self._operation_finished)
        self._workers[operation_token] = worker
        self._active_request = request
        self._busy = True
        self._idle_autosave_timer.stop()
        message = {
            "automatic": "Auto-saving workspace…",
            "manual": "Saving workspace…",
            "snapshot": "Creating snapshot…",
            "rollback": "Rolling back workspace…",
            "close": "Disconnecting devices and packing workspace…",
        }.get(request.reason, "Saving workspace…")
        self._set_state("saving", message)
        try:
            self._pool.start(worker)
        except Exception:
            session_lease.__exit__(None, None, None)
            self._workers.pop(operation_token, None)
            self._busy = False
            self._active_request = None
            raise
        return True

    @pyqtSlot(object, object, object, object, object)
    def _operation_finished(
        self,
        operation_token: object,
        session: WorkspaceSession,
        request: _OperationRequest,
        result: SaveResult | RollbackResult | None,
        error: Exception | None,
    ) -> None:
        self._workers.pop(operation_token, None)
        self._busy = False
        self._active_request = None
        current = self._welcome.active_session()
        if current is session:
            if error is not None:
                category = "conflict" if isinstance(error, WorkspaceConflictError) else "failed"
                self._set_state(category, "Save conflict" if category == "conflict" else "Save failed")
                message = str(error)
                self.saveFailed.emit(message)
                self.notificationRequested.emit(message, "error")
            elif result is not None:
                save_result = result.save if isinstance(result, RollbackResult) else result
                self._last_saved_at = save_result.saved_at
                self._saved_generation = max(
                    self._saved_generation, request.generation
                )
                if save_result.changed_during_save:
                    self._generation = max(
                        self._generation, request.generation + 1
                    )
                    self._pending_request = self._merge_pending(
                        self._pending_request,
                        _OperationRequest(
                            kind="save",
                            reason="automatic",
                            force=False,
                            create_snapshot=True,
                            snapshot_reason="automatic",
                            generation=self._generation,
                        ),
                    )
                self._refresh_snapshots()
                if self.dirty:
                    self._set_state("unsaved", "Unsaved changes")
                else:
                    self._set_state("saved", "Saved")
                if not save_result.skipped:
                    message = {
                        "rollback": "Workspace rolled back and saved.",
                        "snapshot": "Snapshot created and workspace saved.",
                        "automatic": "Workspace auto-saved.",
                    }.get(request.reason, "Workspace saved.")
                    self.saveCompleted.emit(message)
                    if request.reason != "automatic":
                        self.notificationRequested.emit(message, "success")
                if request.kind == "close":
                    self._pending_request = None
                    self._welcome.closeProject()
                    self.workspaceCloseCompleted.emit()
                    return

        pending = self._pending_request
        self._pending_request = None
        if pending is not None and self._welcome.active_session() is session:
            self._start(pending)

    @staticmethod
    def _merge_pending(
        current: _OperationRequest | None, incoming: _OperationRequest
    ) -> _OperationRequest:
        if current is None:
            return incoming
        priority = {
            ("save", "automatic"): 1,
            ("save", "manual"): 2,
            ("snapshot", "snapshot"): 3,
            ("rollback", "rollback"): 4,
            ("close", "close"): 5,
        }
        incoming_priority = priority.get((incoming.kind, incoming.reason), 0)
        current_priority = priority.get((current.kind, current.reason), 0)
        if incoming_priority >= current_priority:
            return incoming
        return current

    @pyqtSlot()
    def _workspace_changed(self) -> None:
        session = self._welcome.active_session()
        watched = self._watcher.files() + self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        self._generation = 0
        self._saved_generation = 0
        self._pending_request = None
        self._idle_autosave_timer.stop()
        if session is None:
            self._autosave_timer.stop()
            self._snapshots = []
            self.snapshotsChanged.emit()
            self._set_state("no_workspace", "No workspace")
            return
        self._autosave_timer.start()
        watch_paths = [
            str(session.device_network_db),
            str(session.info_collected_db),
            str(session.backup_directory),
        ]
        self._watcher.addPaths(
            [path for path in watch_paths if path]
        )
        self._refresh_snapshots()
        self._set_state("saved", "Saved")

    @pyqtSlot(str)
    def _workspace_file_changed(self, path: str) -> None:
        if not self._shutting_down and self.hasWorkspace:
            self.markDirty()
        watched = self._watcher.files() + self._watcher.directories()
        if path and path not in watched:
            if Path(path).exists():
                self._watcher.addPath(path)

    def _refresh_snapshots(self) -> None:
        session = self._welcome.active_session()
        if session is None or session.is_closed:
            snapshots: list[dict[str, Any]] = []
        else:
            try:
                records = self._service.list_snapshots(session)
            except Exception:
                records = ()
            snapshots = [
                {
                    "id": record.snapshot_id,
                    "createdAt": record.created_at,
                    "health": record.health,
                    "label": record.label,
                    "pinned": record.pinned,
                    "reason": record.reason,
                    "size": record.size,
                    "sourceGeneration": record.source_generation,
                }
                for record in records
            ]
        self._snapshots = snapshots
        self.snapshotsChanged.emit()

    def _set_state(self, state: str, message: str) -> None:
        self._state = state
        self._status_text = message
        self.stateChanged.emit()

    def shutdown(self) -> None:
        self._shutting_down = True
        self._autosave_timer.stop()
        self._idle_autosave_timer.stop()
        watched = self._watcher.files() + self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        self._pending_request = None
        if not self._pool.waitForDone(60_000):
            # Do not release an extracted directory while its writer still
            # owns SQLite/file handles. Shutdown is the one safe place to wait.
            self._pool.waitForDone()
        self._workers.clear()
        session = self._welcome.active_session()
        if session is not None and not session.is_closed:
            try:
                self._service.save_project(
                    session, reason="shutdown", force=False
                )
            except Exception as exc:
                # Shutdown must continue; the last committed .ntp remains valid
                # because the package writer never replaces it before verify.
                print(
                    f"Workspace shutdown save failed ({type(exc).__name__}): {exc}",
                    file=sys.stderr,
                )
            finally:
                # The writer owns the application shutdown transaction: once
                # its final save attempt is complete, retire the extracted
                # session immediately instead of relying on a later caller.
                self._welcome.closeProject()


__all__ = ["WorkspaceSaveController"]
