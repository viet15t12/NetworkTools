import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSettings, QUrl, pyqtProperty, pyqtSignal, pyqtSlot

from infrastructure.database.recent_projects import RecentProjectRepository
from infrastructure.workspace import (
    WorkspacePackageError,
    WorkspacePasswordRequired,
    WorkspaceService,
    WorkspaceSession,
)


def _format_relative_timestamp(ts: float) -> str:
    if not ts:
        return "Unknown"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    now = datetime.now().astimezone()
    delta_seconds = int((now - dt).total_seconds())

    if delta_seconds < 60:
        return "Just now"
    if delta_seconds < 3600:
        minutes = delta_seconds // 60
        return f"{minutes}m ago"

    dt_date = dt.date()
    now_date = now.date()
    if dt_date == now_date:
        return f"Today, {dt.strftime('%H:%M')}"
    if (now_date - dt_date).days == 1:
        return f"Yesterday, {dt.strftime('%H:%M')}"
    if now_date.year == dt_date.year:
        return dt.strftime("%d %b, %H:%M")
    return dt.strftime("%d %b %Y")


def _parse_opened_at(value: str) -> datetime:
    try:
        opened_at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    return opened_at


def _format_opened_at(value: str) -> str:
    opened_at = _parse_opened_at(value).astimezone()
    if opened_at.timestamp() <= 0:
        return "Unknown"
    return opened_at.strftime("%d/%m/%Y %H:%M:%S")


class WelcomeController(QObject):
    """Expose project create/open lifecycle operations to QML."""

    recentProjectsChanged = pyqtSignal()
    workspaceRequested = pyqtSignal(str, str)
    welcomeRequested = pyqtSignal(str)
    passwordRequired = pyqtSignal(str)
    operationFailed = pyqtSignal(str, str)
    activeWorkspaceChanged = pyqtSignal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        workspace_service: WorkspaceService | None = None,
        default_project_directory: str | Path | None = None,
        recent_project_repository: RecentProjectRepository | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = QSettings()
        self._workspace_service = workspace_service or WorkspaceService()
        self._recent_project_repository = (
            recent_project_repository or RecentProjectRepository()
        )
        self._default_project_directory = Path(
            default_project_directory or (Path.home() / "Documents")
        ).expanduser()
        self._active_session: WorkspaceSession | None = None
        self._pending_encrypted_path: Path | None = None

        self._migrate_legacy_recents()
        self._recent_projects: list[dict[str, Any]] = self._load_recents()

    def _load_recents(self) -> list[dict[str, Any]]:
        self._recent_project_repository.remove_missing_files()
        projects = []
        for item in self._recent_project_repository.list():
            opened_at = str(item["opened_at"])
            opened_datetime = _parse_opened_at(opened_at)
            projects.append({
                "id": str(item["path"]),
                "name": str(item["name"]),
                "path": str(item["path"]),
                "url": str(item["project_url"]),
                "openedAt": opened_at,
                "openedAtDisplay": _format_opened_at(opened_at),
                "timestamp": opened_datetime.timestamp(),
                "lastOpened": _format_relative_timestamp(opened_datetime.timestamp()),
                "isEncrypted": bool(item["is_encrypted"]),
            })
        return projects

    def _migrate_legacy_recents(self) -> None:
        """Import the former QSettings JSON history once, then retire its key."""

        raw = self._settings.value("Welcome/recentProjects", "")
        if not raw:
            return
        try:
            items = json.loads(str(raw))
            if not isinstance(items, list):
                return
            for item in reversed(items):
                if not isinstance(item, dict) or "path" not in item:
                    continue
                project_path = Path(str(item["path"])).expanduser().resolve()
                if not project_path.is_file():
                    continue
                timestamp = float(item.get("timestamp", 0))
                opened_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                self._recent_project_repository.record(
                    str(item.get("name") or project_path.stem),
                    project_path,
                    is_encrypted=bool(item.get("isEncrypted", False)),
                    opened_at=opened_at,
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        self._settings.remove("Welcome/recentProjects")
        self._settings.sync()

    def _record_recent(self, name: str, path: Path, is_encrypted: bool = False) -> None:
        p = path.resolve()
        self._recent_project_repository.record(
            name or p.stem,
            p,
            is_encrypted=is_encrypted,
        )
        self._recent_projects = self._load_recents()
        self.recentProjectsChanged.emit()

    @pyqtSlot(str)
    def removeRecent(self, project_id: str) -> None:
        wanted = (project_id or "").strip()
        before_len = len(self._recent_projects)
        self._recent_projects = [
            item for item in self._recent_projects
            if item.get("id") != wanted and item.get("path") != wanted
        ]
        if len(self._recent_projects) != before_len:
            self._recent_project_repository.remove(wanted)
            self.recentProjectsChanged.emit()

    def get_most_recent_project(self) -> dict[str, Any] | None:
        """Return the most recent existing project entry if available."""
        for item in self._recent_projects:
            p = Path(str(item.get("path", "")))
            if p.is_file():
                return item
        return None

    @pyqtProperty("QVariantList", notify=recentProjectsChanged)
    def recentProjects(self) -> list[dict[str, Any]]:
        return [dict(project) for project in self._recent_projects]

    @pyqtProperty(str, notify=activeWorkspaceChanged)
    def activeProjectPath(self) -> str:
        return str(self._active_session.project_path) if self._active_session else ""

    @pyqtProperty(str, notify=activeWorkspaceChanged)
    def activeWorkspacePath(self) -> str:
        return (
            str(self._active_session.working_directory)
            if self._active_session
            else ""
        )

    @pyqtProperty(bool, notify=activeWorkspaceChanged)
    def activeProjectEncrypted(self) -> bool:
        return bool(self._active_session and self._active_session.encrypted)

    def active_session(self) -> WorkspaceSession | None:
        """Return the Python session object for lifecycle coordinators."""

        return self._active_session

    @property
    def workspace_service(self) -> WorkspaceService:
        return self._workspace_service

    def _activate(self, session: WorkspaceSession) -> None:
        previous = self._active_session
        self._active_session = session
        self._pending_encrypted_path = None
        if previous is not None and previous is not session:
            previous.close()
        self._record_recent(
            session.manifest.name,
            session.project_path,
            is_encrypted=session.encrypted,
        )
        self.activeWorkspaceChanged.emit()
        self.workspaceRequested.emit(session.manifest.name, str(session.project_path))

    @pyqtSlot(str)
    def openRecent(self, project_id: str) -> None:
        wanted = (project_id or "").strip()
        project = next(
            (entry for entry in self._recent_projects
             if entry.get("id") == wanted or entry.get("path") == wanted),
            None,
        )
        if project is None:
            return
        self._open_path(Path(str(project["path"])), password=None)

    @pyqtSlot(str)
    @pyqtSlot(str, str)
    def createProject(self, project_name: str, password: str = "") -> None:
        """Create under the default project folder; blank password means plain ZIP."""

        name = (project_name or "").strip() or "Untitled Project"
        target = self._default_project_directory / f"{self._project_stem(name)}.ntp"
        self._create_at(name, target, password)

    @pyqtSlot(str, QUrl, str)
    def createProjectIn(
        self, project_name: str, folder_url: QUrl, password: str = ""
    ) -> None:
        """Create ``<project-name>.ntp`` inside a selected local folder."""

        if not folder_url.isLocalFile():
            self.operationFailed.emit("Create Project", "Choose a local folder.")
            return
        folder_text = folder_url.toLocalFile().strip()
        folder = Path(folder_text) if folder_text else None
        if folder is None or not folder.is_dir():
            self.operationFailed.emit("Create Project", "Choose an existing folder.")
            return
        name = (project_name or "").strip() or "Untitled Project"
        self._create_at(
            name,
            folder / f"{self._project_stem(name)}.ntp",
            password,
        )

    @pyqtSlot(str, QUrl, str)
    def createProjectAt(
        self, project_name: str, project_url: QUrl, password: str = ""
    ) -> None:
        """Create at an explicit local file URL for the completed location picker."""

        if not project_url.isLocalFile():
            self.operationFailed.emit("Create Project", "Choose a local project path.")
            return
        local_path = project_url.toLocalFile().strip()
        if not local_path:
            self.operationFailed.emit("Create Project", "Choose a project path.")
            return
        self._create_at((project_name or "").strip(), Path(local_path), password)

    def _create_at(self, name: str, target: Path, password: str) -> None:
        if target.suffix.lower() != ".ntp":
            target = target.with_name(target.name + ".ntp")
        try:
            session = self._workspace_service.create_project(
                name or "Untitled Project",
                target,
                password=password or None,
            )
        except (OSError, ValueError, WorkspacePackageError) as exc:
            self.operationFailed.emit("Create Project", str(exc))
            return
        self._activate(session)

    @staticmethod
    def _project_stem(name: str) -> str:
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
        return safe_stem or "Untitled-Project"

    @pyqtSlot(QUrl)
    def openProject(self, project_url: QUrl) -> None:
        if not project_url.isLocalFile():
            self.operationFailed.emit("Open Project", "Choose a local .ntp file.")
            return
        local_path = project_url.toLocalFile().strip()
        if not local_path:
            self.operationFailed.emit("Open Project", "Choose a project file.")
            return
        self._open_path(Path(local_path), password=None)

    @pyqtSlot(str)
    def unlockProject(self, password: str) -> None:
        """Retry the pending encrypted project without persisting the password."""

        path = self._pending_encrypted_path
        if path is None:
            return
        self._open_path(path, password=password)

    def _open_path(self, path: Path, password: str | None) -> None:
        try:
            session = self._workspace_service.open_project(path, password=password)
        except WorkspacePasswordRequired:
            self._pending_encrypted_path = path
            self.passwordRequired.emit(str(path))
            return
        except (OSError, ValueError, WorkspacePackageError) as exc:
            self.operationFailed.emit("Open Project", str(exc))
            return
        self._activate(session)

    @pyqtSlot()
    def closeProject(self) -> None:
        session = self._active_session
        self._active_session = None
        self._pending_encrypted_path = None
        if session is not None:
            session.close()
            self.activeWorkspaceChanged.emit()

    def shutdown(self) -> None:
        self.closeProject()

    @pyqtSlot(str)
    def requestWelcome(self, mode: str = "") -> None:
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode not in {"", "create", "open", "settings"}:
            normalized_mode = ""
        self.welcomeRequested.emit(normalized_mode)


__all__ = ["WelcomeController"]
