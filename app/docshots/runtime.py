"""Qt/QML composition, fixture lifecycle, and framebuffer capture."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .environment import configure_qt_environment
from .shots import VLAN_WORKFLOW_FILENAMES, ShotSpec

configure_qt_environment()

import main as _main_bootstrap  # noqa: F401 - configures PyQt DLL/QML paths
from PyQt6.QtCore import (
    QCoreApplication,
    QEvent,
    QEventLoop,
    QObject,
    QPoint,
    QPointF,
    QSettings,
    QSize,
    QThread,
    Qt,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor, QImage, QImageReader, QPainter
from PyQt6.QtQml import QJSValue, QQmlApplicationEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app_facade import (
    AppPaths,
    DatabaseManager,
    ExternalToolsManager,
    MenuPresentationController,
    QML_MODULE_DIR,
    StatusBarSettings,
    ThemeSettings,
    WindowSettings,
)
from features.config_backup import ConfigBackupService
from features.config_sync import ConfigSyncService
from features.devices import DeviceRepository
from features.sftp import SftpController
from features.syslog import SyslogManager
from infrastructure.database.paths import (
    DEVICE_NETWORK_SCHEMA_DIR,
    INFO_COLLECTED_SCHEMA_DIR,
)
from infrastructure.network.session_registry import DeviceSessionRegistry
from scripts.build_databases import build_database


VLAN_FIXTURE_HOST = "192.0.2.11"
VLAN_FIXTURE_ROWS = (
    (1, "default", "active"),
    (10, "Management", "active"),
    (20, "Users", "active"),
)
VLAN_CREATED_ROW = (30, "Guest", "active")


class DocshotError(RuntimeError):
    """A deterministic rendering or capture step failed."""


@dataclass(frozen=True, slots=True)
class RenderRequest:
    width: int
    height: int
    scale: float
    theme: str
    output_dir: Path
    timeout_ms: int = 10_000

    @property
    def pixel_size(self) -> QSize:
        return QSize(round(self.width * self.scale), round(self.height * self.scale))


@dataclass(frozen=True, slots=True)
class RenderResult:
    path: Path
    width: int
    height: int


class DocumentationTerminal(QObject):
    """Network-free implementation of the terminal/session QML contract."""

    taskStarted = pyqtSignal(str)
    taskProgress = pyqtSignal(str)
    taskFinished = pyqtSignal(bool, str)
    connectHostFinished = pyqtSignal(str, bool, str)
    deviceSessionFinished = pyqtSignal(str, bool, str)
    deviceSessionClosed = pyqtSignal(str)
    deviceCommandFinished = pyqtSignal(str, str, bool, str, str)
    runningConfigFinished = pyqtSignal(str, bool, str)
    saveConfigFinished = pyqtSignal(str, bool, str)
    manualSyncPreviewFinished = pyqtSignal(str, bool, str, object)
    batchStarted = pyqtSignal(str, str, int)
    hostOperationChanged = pyqtSignal(str, str, str, str, int)
    batchProgress = pyqtSignal(str, int, int, int, int)
    batchFinished = pyqtSignal(str, bool, object)
    sessionStateChanged = pyqtSignal(str, str, str)
    terminalStateChanged = pyqtSignal(str, str)
    terminalError = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.shut_down = False

    @pyqtSlot(result="QVariant")
    def ensurePythonLoginDeps(self) -> dict[str, object]:
        return {
            "ok": True,
            "statusText": "DOC FIXTURE",
            "message": "Documentation fixture is ready; network I/O is disabled.",
        }

    @pyqtSlot(str, result=bool)
    def hasDeviceSession(self, _host: str) -> bool:
        return True

    @pyqtSlot(str, result=bool)
    def openDeviceSessionAsync(self, _host: str) -> bool:
        return True

    @pyqtSlot(str, result=str)
    def deviceTerminalState(self, _host: str) -> str:
        return "closed"

    @pyqtSlot(str, result="QVariant")
    def openDeviceTerminal(self, host: str) -> dict[str, object]:
        return {"ok": False, "message": f"External terminal disabled for {host}."}

    @pyqtSlot(str, result="QVariant")
    def pingHost(self, host: str) -> dict[str, object]:
        return {"ok": False, "severity": "info", "message": f"Network disabled for {host}."}

    @pyqtSlot(str, result=bool)
    def connectHostAndSyncAsync(self, _host: str) -> bool:
        return False

    @pyqtSlot("QVariant", result="QVariant")
    def connectHostsAndSyncAsync(self, _hosts: Any) -> dict[str, object]:
        return {"ok": False, "accepted": [], "rejected": [], "message": "Network disabled."}

    @pyqtSlot(str, result=bool)
    def saveDeviceConfigAsync(self, _host: str) -> bool:
        return False

    @pyqtSlot("QVariantList", result=str)
    def connectHostsAsync(self, _hosts: list[str]) -> str:
        return ""

    @pyqtSlot("QVariantList", result=str)
    def getRunningConfigsAsync(self, _hosts: list[str]) -> str:
        return ""

    @pyqtSlot("QVariantList", result=str)
    def disconnectHostsAsync(self, _hosts: list[str]) -> str:
        return ""

    @pyqtSlot(str, result=bool)
    def cancelBatch(self, _batch_id: str) -> bool:
        return False

    @pyqtSlot(str, result=bool)
    def manualSyncAsync(self, _host: str) -> bool:
        return False

    @pyqtSlot(str, str, result=bool)
    def applyManualSyncAsync(self, _host: str, _mode: str) -> bool:
        return False

    @pyqtSlot(str, result="QVariant")
    def closeDeviceSession(self, host: str) -> dict[str, object]:
        self.deviceSessionClosed.emit(host)
        return {"ok": True, "message": "Fixture session closed."}

    def shutdown(self) -> None:
        self.shut_down = True


class DocumentationNetworkMonitor(QObject):
    networkChanged = pyqtSignal()
    systemInfoChanged = pyqtSignal()

    @pyqtProperty(bool, constant=True)
    def isConnected(self) -> bool:
        return False

    @pyqtProperty(str, constant=True)
    def connectionType(self) -> str:
        return "none"

    @pyqtProperty(str, constant=True)
    def networkName(self) -> str:
        return ""

    @pyqtProperty("QVariantList", constant=True)
    def virtualLabs(self) -> list[object]:
        return []

    @pyqtProperty(int, constant=True)
    def virtualLabCount(self) -> int:
        return 0

    @pyqtProperty(str, constant=True)
    def virtualLabName(self) -> str:
        return ""

    @pyqtProperty(str, constant=True)
    def virtualLabState(self) -> str:
        return "offline"

    @pyqtProperty(bool, constant=True)
    def virtualLabActive(self) -> bool:
        return False

    @pyqtProperty(str, constant=True)
    def virtualLabPlatform(self) -> str:
        return ""

    @pyqtProperty(str, constant=True)
    def virtualLabServerIp(self) -> str:
        return ""

    @pyqtProperty(str, constant=True)
    def virtualLabUrl(self) -> str:
        return ""

    @pyqtProperty(str, constant=True)
    def virtualLabNameDetected(self) -> str:
        return ""

    @pyqtProperty(str, constant=True)
    def virtualLabDetail(self) -> str:
        return ""

    @pyqtProperty(int, constant=True)
    def virtualLabRunningNodeCount(self) -> int:
        return 0

    @pyqtProperty(int, constant=True)
    def ramUsagePercent(self) -> int:
        return 0

    def shutdown(self) -> None:
        pass


class DocumentationSystemAppearance(QObject):
    appearanceChanged = pyqtSignal()

    @pyqtProperty(int, constant=True)
    def colorScheme(self) -> int:
        return 1

    @pyqtProperty(bool, constant=True)
    def prefersDark(self) -> bool:
        return False


class DocumentationWelcomeController(QObject):
    recentProjectsChanged = pyqtSignal()
    workspaceRequested = pyqtSignal(str, str)
    welcomeRequested = pyqtSignal(str)
    passwordRequired = pyqtSignal(str)
    operationFailed = pyqtSignal(str, str)
    activeWorkspaceChanged = pyqtSignal()
    defaultProjectDirectoryChanged = pyqtSignal()

    _RECENTS = [
        {
            "id": "doc-core-lab",
            "name": "Core Lab",
            "path": "/documentation/networktools/Core-Lab.ntp",
            "url": "file:///documentation/networktools/Core-Lab.ntp",
            "openedAtDisplay": "20/08/2026 09:42:00",
            "lastOpened": "20 Aug 2026",
            "isMock": True,
        },
        {
            "id": "doc-campus-network",
            "name": "Campus Network",
            "path": "/documentation/networktools/Campus-Network.ntp",
            "url": "file:///documentation/networktools/Campus-Network.ntp",
            "openedAtDisplay": "19/08/2026 16:10:00",
            "lastOpened": "19 Aug 2026",
            "isMock": True,
        },
        {
            "id": "doc-branch-rollout",
            "name": "Branch Rollout",
            "path": "/documentation/networktools/Branch-Rollout.ntp",
            "url": "file:///documentation/networktools/Branch-Rollout.ntp",
            "openedAtDisplay": "18/08/2026 13:25:00",
            "lastOpened": "18 Aug 2026",
            "isMock": True,
        },
    ]

    @pyqtProperty("QVariantList", notify=recentProjectsChanged)
    def recentProjects(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._RECENTS]

    @pyqtProperty(str, notify=defaultProjectDirectoryChanged)
    def defaultProjectDirectory(self) -> str:
        return "/documentation/networktools"

    @pyqtSlot(str, result=QUrl)
    def folderUrlForPath(self, folder_path: str) -> QUrl:
        return QUrl.fromLocalFile(folder_path or self.defaultProjectDirectory)

    @pyqtSlot(QUrl, result=str)
    def localPathFromUrl(self, folder_url: QUrl) -> str:
        return folder_url.toLocalFile() if folder_url.isLocalFile() else ""

    @pyqtSlot(str, result=bool)
    def projectLocationIsDefault(self, folder_path: str) -> bool:
        return folder_path == self.defaultProjectDirectory

    @pyqtSlot(str)
    def requestWelcome(self, mode: str) -> None:
        self.welcomeRequested.emit(mode)

    @pyqtSlot(str)
    def openRecent(self, project_id: str) -> None:
        project = next((item for item in self._RECENTS if item["id"] == project_id), None)
        if project:
            self.workspaceRequested.emit(str(project["name"]), str(project["path"]))

    @pyqtSlot(str)
    def openProject(self, _project_url: str) -> None:
        pass

    @pyqtSlot(str, str, str)
    def createProjectIn(self, _name: str, _folder_url: str, _password: str) -> None:
        pass

    @pyqtSlot(str, str, str, bool, result=bool)
    def createProjectInPath(
        self, _name: str, _folder_path: str, _password: str, _set_default: bool
    ) -> bool:
        return True

    @pyqtSlot(str)
    def unlockProject(self, _password: str) -> None:
        pass

    @pyqtSlot(str)
    def removeRecent(self, _project_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


class DocumentationWorkspaceController(QObject):
    stateChanged = pyqtSignal()
    snapshotsChanged = pyqtSignal()
    notificationRequested = pyqtSignal(str, str)
    saveCompleted = pyqtSignal(str)
    saveFailed = pyqtSignal(str)
    workspaceCloseCompleted = pyqtSignal()

    @pyqtProperty(bool, constant=True)
    def hasWorkspace(self) -> bool:
        return True

    @pyqtProperty(bool, constant=True)
    def busy(self) -> bool:
        return False

    @pyqtProperty(bool, constant=True)
    def dirty(self) -> bool:
        return False

    @pyqtProperty(str, constant=True)
    def state(self) -> str:
        return "saved"

    @pyqtProperty(str, constant=True)
    def statusText(self) -> str:
        return "All changes saved"

    @pyqtProperty(str, constant=True)
    def lastSavedAt(self) -> str:
        return "20/08/2026 09:45"

    @pyqtProperty("QVariantList", constant=True)
    def snapshots(self) -> list[object]:
        return []

    @pyqtSlot(result=bool)
    def requestManualSave(self) -> bool:
        return True

    @pyqtSlot(result=bool)
    def requestCloseWorkspace(self) -> bool:
        return True

    @pyqtSlot(str, result=bool)
    def createSnapshot(self, _label: str = "") -> bool:
        return True

    @pyqtSlot(str, result=bool)
    def rollbackSnapshot(self, _snapshot_id: str) -> bool:
        return True

    def shutdown(self) -> None:
        pass


class FixtureBundle:
    """Own every temporary backend made visible to one QML engine."""

    def __init__(self, request: RenderRequest) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="networktools-docshots-")
        self.root = Path(self._temporary.name)
        self._closed = False
        self._configure_settings(request)

        self.device_db = self.root / "data" / "device_network.db"
        self.info_db = self.root / "data" / "info_collected.db"
        build_database(DEVICE_NETWORK_SCHEMA_DIR, self.device_db)
        build_database(INFO_COLLECTED_SCHEMA_DIR, self.info_db)

        repository = DeviceRepository(self.device_db)
        backup_service = ConfigBackupService(self.root / "backup")
        sync_service = ConfigSyncService(self.device_db, repository.get_role)
        registry = DeviceSessionRegistry(lambda _host: None)
        self.db_manager = DatabaseManager(
            db_path=self.device_db,
            info_db_path=self.info_db,
            config_backup_service=backup_service,
            config_sync_service=sync_service,
            session_registry=registry,
        )
        self._populate_devices()
        self._populate_vlans()

        self.cli = DocumentationTerminal()
        self.status_bar_settings = StatusBarSettings()
        for name in ("showDate", "showTime", "showNetwork", "showNetworkName", "showRam"):
            setattr(self.status_bar_settings, name, False)
        self.network_monitor = DocumentationNetworkMonitor()
        self.theme_settings = ThemeSettings()
        self.theme_settings.themeMode = 1 if request.theme == "light" else 2
        self.theme_settings.highContrast = False
        self.theme_settings.lightDarkSideBar = False
        self.theme_settings.useSystemAccentColor = False
        self.theme_settings.useCustomAccentColor = False
        self.menu_presentation = MenuPresentationController()
        self.system_appearance = DocumentationSystemAppearance()
        self.window_settings = WindowSettings()
        self.welcome_controller = DocumentationWelcomeController()
        self.workspace_controller = DocumentationWorkspaceController()
        self.app_paths = AppPaths()
        self.external_tools = ExternalToolsManager(
            db_path=self.root / "external_tools.db",
            device_db_path=self.device_db,
        )
        self.sftp_controller = SftpController(
            settings=QSettings(),
            device_login_service=None,
        )
        self.syslog_manager = SyslogManager()
        self.syslog_manager.set_database_paths(self.info_db, self.device_db)

    def _configure_settings(self, request: RenderRequest) -> None:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            str(self.root / "settings"),
        )
        app = QCoreApplication.instance()
        if app is not None:
            app.setOrganizationName("NetworkToolsDocumentation")
            app.setApplicationName("Docshots")
        settings = QSettings()
        settings.clear()
        settings.setValue("Window/isFirstLaunch", False)
        settings.setValue("Window/isMaximized", False)
        settings.setValue("Window/savedX", 0)
        settings.setValue("Window/savedY", 0)
        settings.setValue("Window/savedWidth", request.width)
        settings.setValue("Window/savedHeight", request.height)
        settings.setValue("Appearance/menuStyle", "custom")
        settings.setValue("SFTP/defaultLocalPath", str(self.root / "sftp"))
        settings.sync()
        (self.root / "sftp").mkdir(parents=True, exist_ok=True)

    def _populate_devices(self) -> None:
        rows = (
            ("192.0.2.1", "R1", "rou", "connected"),
            ("192.0.2.2", "R2", "rou", "waiting"),
            ("192.0.2.11", "SW1", "sw2", "connected"),
        )
        for host, name, role, status in rows:
            if not self.db_manager.addDevice(
                host, name, "SSH", "22", "admin", "fixture-not-a-secret",
                "cisco_ios", role, "",
            ):
                raise DocshotError(f"Could not create fixture device {host}.")
            if not self.db_manager.updateDeviceConnectionStatus(host, status):
                raise DocshotError(f"Could not set fixture status for {host}.")

    def _populate_vlans(self) -> None:
        for vlan_id, vlan_name, state in VLAN_FIXTURE_ROWS:
            result = self.db_manager.saveSwitchVlan(
                VLAN_FIXTURE_HOST,
                {
                    "id": 0,
                    "vlan_id": vlan_id,
                    "vlan_name": vlan_name,
                    "state": state,
                },
            )
            if not result.get("ok"):
                raise DocshotError(
                    f"Could not create fixture VLAN {vlan_id}: {result.get('message', '')}"
                )

        # The fixture inventory represents state already present on the switch.
        # Only VLAN 30, created through the documented UI flow, should be pending
        # and therefore appear in the View & Push preview.
        with closing(self.db_manager._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE t06_vlan_db
                    SET success = 'synchronized', device_present = 1
                    WHERE host = ?;
                    """,
                    (VLAN_FIXTURE_HOST,),
                )

    def context_properties(self) -> dict[str, object]:
        return {
            "dbManager": self.db_manager,
            "cli": self.cli,
            "networkMonitor": self.network_monitor,
            "statusBarSettings": self.status_bar_settings,
            "themeSettings": self.theme_settings,
            "menuPresentation": self.menu_presentation,
            "systemAppearance": self.system_appearance,
            "windowSettings": self.window_settings,
            "welcomeController": self.welcome_controller,
            "workspaceSaveController": self.workspace_controller,
            "AppPaths": self.app_paths,
            "externalTools": self.external_tools,
            "sftpController": self.sftp_controller,
            "syslogManager": self.syslog_manager,
            "syslogSettings": self.syslog_manager.settings,
            "nqvEasterEggEnabled": False,
            "ptitEasterEggEnabled": False,
            "documentationMode": True,
        }

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.syslog_manager.shutdown()
        self.sftp_controller.shutdown()
        self.db_manager.shutdown()
        self.cli.shutdown()
        self.workspace_controller.shutdown()
        self.welcome_controller.shutdown()
        self._temporary.cleanup()

    def __enter__(self) -> "FixtureBundle":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.shutdown()


def _application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["networktools-docshots"])
    app.setOrganizationName("NetworkToolsDocumentation")
    app.setOrganizationDomain("documentation.invalid")
    app.setApplicationName("Docshots")
    return app


def _wait_until(
    app: QApplication,
    predicate: Callable[[], bool],
    timeout_ms: int,
    description: str,
) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 25)
        if predicate():
            return
        QThread.msleep(5)
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 25)
    if not predicate():
        raise DocshotError(f"Timed out waiting for {description} ({timeout_ms} ms).")


def capture_item(item: QQuickItem, pixel_size: QSize, timeout_ms: int = 10_000) -> QImage:
    """Render one Qt Quick item into a true target-resolution QImage."""

    if pixel_size.width() <= 0 or pixel_size.height() <= 0:
        raise DocshotError("Capture size must be positive.")
    result = item.grabToImage(pixel_size)
    if result is None:
        raise DocshotError("QQuickItem.grabToImage() did not start.")
    app = _application()
    _wait_until(
        app,
        lambda: not result.image().isNull(),
        timeout_ms,
        "QQuickItem image render",
    )
    image = result.image()
    if image.isNull():
        raise DocshotError("QQuickItem capture returned a null image.")
    if image.size() != pixel_size:
        raise DocshotError(
            f"Qt returned {image.width()}x{image.height()}, expected "
            f"{pixel_size.width()}x{pixel_size.height()}."
        )
    return image


def capture_window(window: QQuickWindow, scale: float, timeout_ms: int = 10_000) -> QImage:
    """Capture a full QML window, supersampling through the scene graph when needed."""

    logical_size = window.size()
    pixel_size = QSize(
        round(logical_size.width() * scale),
        round(logical_size.height() * scale),
    )
    if abs(scale - 1.0) < 1e-9:
        image = window.grabWindow()
        if not image.isNull() and image.size() == pixel_size:
            return image
    return capture_item(window.contentItem(), pixel_size, timeout_ms)


def _digest(image: QImage) -> bytes:
    normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return hashlib.sha256(normalized.bits().asstring(normalized.sizeInBytes())).digest()


def _wait_for_stable_scene(
    app: QApplication,
    engine: QQmlApplicationEngine,
    window: QQuickWindow,
    timeout_ms: int,
) -> None:
    controller = engine.incubationController()
    if controller is not None:
        _wait_until(
            app,
            lambda: controller.incubatingObjectCount() == 0,
            timeout_ms,
            "asynchronous QML components",
        )

    deadline = time.monotonic() + timeout_ms / 1000
    previous: bytes | None = None
    while time.monotonic() < deadline:
        window.requestUpdate()
        image = capture_item(window.contentItem(), window.size(), timeout_ms)
        current = _digest(image)
        if current == previous:
            return
        previous = current
        settle_deadline = min(deadline, time.monotonic() + 0.08)
        while time.monotonic() < settle_deadline:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            QThread.msleep(5)
    raise DocshotError("The QML scene did not become visually stable before timeout.")


def _prepare_window(
    app: QApplication,
    engine: QQmlApplicationEngine,
    window: QQuickWindow,
    shot: ShotSpec,
    request: RenderRequest,
) -> None:
    window.setMinimumSize(QSize(1, 1))
    window.setMaximumSize(QSize(16_384, 16_384))
    window.showNormal()
    window.resize(request.width, request.height)
    window.setPosition(QPoint(0, 0))
    if shot.workspace_name:
        window.setProperty("workspaceDisplayName", shot.workspace_name)
        window.setProperty(
            "workspacePath", "/documentation/networktools/Campus-Network.ntp"
        )
    window.show()
    _wait_until(
        app,
        lambda: (
            window.isVisible()
            and window.width() == request.width
            and window.height() == request.height
            and window.contentItem().width() == request.width
            and window.contentItem().height() == request.height
        ),
        request.timeout_ms,
        "fixed QML window geometry",
    )

    if shot.selected_host:
        sidebar = window.findChild(QObject, "mainPanelSideBar")
        if sidebar is None:
            raise DocshotError("The workspace sidebar was not created.")
        activate = getattr(sidebar, "activateDevice", None)
        if not callable(activate):
            raise DocshotError("The workspace sidebar cannot activate fixture devices.")
        activate(shot.selected_host)

    _wait_for_stable_scene(app, engine, window, request.timeout_ms)


def _save_png_atomic(image: QImage, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=".png", dir=destination.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        if not image.save(str(temporary_path), "PNG"):
            raise DocshotError(f"Qt could not encode PNG: {destination}")
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def _to_python(value: Any) -> Any:
    return value.toVariant() if isinstance(value, QJSValue) else value


def _sampled_color_count(image: QImage) -> int:
    colors: set[int] = set()
    for row in range(13):
        y = min(image.height() - 1, round(row * (image.height() - 1) / 12))
        for column in range(17):
            x = min(image.width() - 1, round(column * (image.width() - 1) / 16))
            colors.add(image.pixelColor(x, y).rgba())
    return len(colors)


def _validate_saved_png(path: Path, expected_size: QSize) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise DocshotError(f"PNG was not created or is empty: {path}")
    reader = QImageReader(str(path), b"PNG")
    if not reader.canRead():
        raise DocshotError(f"PNG cannot be read: {path}: {reader.errorString()}")
    if reader.size() != expected_size:
        raise DocshotError(
            f"PNG {path.name} is {reader.size().width()}x{reader.size().height()}, "
            f"expected {expected_size.width()}x{expected_size.height()}."
        )
    image = reader.read()
    if image.isNull():
        raise DocshotError(f"PNG decoded to a null image: {path}: {reader.errorString()}")
    if _sampled_color_count(image) < 2:
        raise DocshotError(f"PNG appears blank or visually empty: {path}")


def _is_visible_item(value: QObject) -> bool:
    return isinstance(value, QQuickItem) and value.isVisible() and value.opacity() > 0


def _visual_items(root: QObject) -> list[QQuickItem]:
    if isinstance(root, QQuickWindow):
        pending = [root.contentItem()]
    elif isinstance(root, QQuickItem):
        pending = [root]
    else:
        pending = [
            child for child in root.findChildren(QQuickItem) if child.parentItem() is None
        ]
    result: list[QQuickItem] = []
    while pending:
        item = pending.pop()
        result.append(item)
        pending.extend(item.childItems())
    return result


def _find_visible_item(
    root: QObject,
    property_name: str,
    expected: Any,
    description: str,
) -> QQuickItem:
    available: list[str] = []
    for candidate in _visual_items(root):
        value = _to_python(candidate.property(property_name))
        if value not in (None, "") and len(available) < 20:
            available.append(f"{value!r}/{_is_visible_item(candidate)}")
        if _is_visible_item(candidate) and value == expected:
            return candidate
    detail = ", ".join(available) if available else "no matching properties"
    raise DocshotError(
        f"Could not find visible QML item for {description}; saw {detail}."
    )


def _find_visible_named_item(root: QObject, object_name: str) -> QQuickItem:
    candidates = [
        candidate
        for candidate in _visual_items(root)
        if candidate.objectName() == object_name and _is_visible_item(candidate)
    ]
    if len(candidates) != 1:
        raise DocshotError(
            f"Expected one visible QML item named {object_name!r}, found {len(candidates)}."
        )
    return candidates[0]


def _click_item(window: QQuickWindow, item: QQuickItem, y_ratio: float = 0.5) -> None:
    if not item.isEnabled():
        name = item.objectName() or item.metaObject().className()
        raise DocshotError(f"QML item {name} is disabled.")
    local = QPointF(item.width() / 2, item.height() * y_ratio)
    scene = item.mapToScene(local)
    point = QPoint(round(scene.x()), round(scene.y()))
    if not window.geometry().contains(point):
        raise DocshotError(
            f"QML click target is outside the application window at {point.x()},{point.y()}."
        )
    QTest.mouseClick(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        point,
    )


def _send_key(window: QQuickWindow, key: Qt.Key) -> None:
    QTest.keyClick(window, key, Qt.KeyboardModifier.NoModifier)


def _type_text(window: QQuickWindow, value: str) -> None:
    if window.activeFocusItem() is None:
        raise DocshotError("No QML item has focus for text input.")
    for character in value:
        QTest.keyClick(window, character, Qt.KeyboardModifier.NoModifier)


def _focus_standard_text_field(wrapper: QQuickItem) -> QQuickItem:
    for candidate in _visual_items(wrapper):
        if candidate is wrapper:
            continue
        placeholder = candidate.property("placeholderText")
        if placeholder is not None and callable(getattr(candidate, "selectAll", None)):
            candidate.forceActiveFocus()
            return candidate
    raise DocshotError("Could not find the editable control inside StandardTextField.")


def _qml_rows(fixture: FixtureBundle) -> list[dict[str, Any]]:
    return [dict(row) for row in fixture.db_manager.getSwitchVlans(VLAN_FIXTURE_HOST)]


def _row_by_vlan(fixture: FixtureBundle, vlan_id: int) -> dict[str, Any] | None:
    return next(
        (row for row in _qml_rows(fixture) if int(row.get("vlan_id", 0)) == vlan_id),
        None,
    )


def _capture_vlan_step(
    app: QApplication,
    engine: QQmlApplicationEngine,
    window: QQuickWindow,
    request: RenderRequest,
    directory: Path,
    filename: str,
) -> Path:
    _wait_for_stable_scene(app, engine, window, request.timeout_ms)
    image = capture_window(window, request.scale, request.timeout_ms)
    if image.isNull() or image.size() != request.pixel_size:
        raise DocshotError(
            f"Capture {filename} did not match the requested "
            f"{request.pixel_size.width()}x{request.pixel_size.height()} target."
        )
    if image.hasAlphaChannel():
        # A supersampled Popup overlay is rendered by grabToImage() with its
        # translucent dim layer intact. Flatten it at the target resolution so
        # PNG viewers reproduce the same light/dark backing as grabWindow().
        flattened = QImage(image.size(), QImage.Format.Format_RGB32)
        flattened.fill(QColor("#ffffff" if request.theme == "light" else "#202020"))
        painter = QPainter(flattened)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flattened
    path = directory / filename
    _save_png_atomic(image, path)
    _validate_saved_png(path, request.pixel_size)
    return path


def render_vlan_workflow(request: RenderRequest) -> tuple[RenderResult, ...]:
    """Drive the production VLAN QML flow and capture every documentation state."""

    if request.width <= 0 or request.height <= 0 or request.scale <= 0:
        raise DocshotError("Width, height, and scale must be greater than zero.")

    request.output_dir.parent.mkdir(parents=True, exist_ok=True)
    app = _application()
    engine: QQmlApplicationEngine | None = None
    window: QQuickWindow | None = None
    with tempfile.TemporaryDirectory(
        prefix=".vlan-docshots-", dir=request.output_dir.parent
    ) as staging_name, FixtureBundle(request) as fixture:
        staging = Path(staging_name)
        staged_paths: list[Path] = []
        try:
            if _row_by_vlan(fixture, VLAN_CREATED_ROW[0]) is not None:
                raise DocshotError("VLAN 30 unexpectedly exists in the clean fixture.")

            engine = QQmlApplicationEngine()
            engine.addImportPath(str(QML_MODULE_DIR.parent))
            warnings: list[str] = []
            engine.warnings.connect(
                lambda messages: warnings.extend(message.toString() for message in messages)
            )
            context = engine.rootContext()
            for name, value in fixture.context_properties().items():
                context.setContextProperty(name, value)

            engine.loadFromModule("UI", "Main")
            roots = engine.rootObjects()
            if not roots or not isinstance(roots[-1], QQuickWindow):
                detail = f" QML warnings: {' | '.join(warnings)}" if warnings else ""
                raise DocshotError(f"Could not load UI/Main.{detail}")
            window = roots[-1]
            workflow_shot = ShotSpec(
                "vlan",
                "Main",
                workspace_name="Campus Network Lab",
                selected_host=VLAN_FIXTURE_HOST,
            )
            _prepare_window(app, engine, window, workflow_shot, request)

            sidebar = window.findChild(QObject, "mainPanelSideBar")
            if sidebar is None or str(sidebar.property("activeHost")) != VLAN_FIXTURE_HOST:
                raise DocshotError("SW1 was not selected in the device workspace.")
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[0]
                )
            )

            switching_item = _find_visible_item(
                window, "text", "Switching", "the Switching feature"
            )
            _click_item(window, switching_item)
            _wait_until(
                app,
                lambda: (
                    (workspace := window.findChild(QObject, "loadedSwitchWorkspace"))
                    is not None
                    and str(workspace.property("feature")) == "switching"
                    and str(workspace.property("subFeature")) == "vlan"
                ),
                request.timeout_ms,
                "Switching > VLAN navigation",
            )
            vlan_loader = window.findChild(QObject, "switchVlanLoader")
            _wait_until(
                app,
                lambda: vlan_loader is not None and vlan_loader.property("item") is not None,
                request.timeout_ms,
                "VLAN page",
            )
            vlan_page = vlan_loader.property("item")
            _wait_until(
                app,
                lambda: len(_to_python(vlan_page.property("allRows")) or []) == 3,
                request.timeout_ms,
                "initial VLAN inventory",
            )
            if [int(row["vlan_id"]) for row in _qml_rows(fixture)] != [1, 10, 20]:
                raise DocshotError("The initial VLAN fixture is not VLAN 1, 10, and 20.")
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[1]
                )
            )

            add_button = _find_visible_named_item(vlan_page, "vlanAddButton")
            _click_item(window, add_button)
            _wait_until(
                app,
                lambda: int(vlan_page.property("formMode") or 0) == 1,
                request.timeout_ms,
                "VLAN create form",
            )
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[2]
                )
            )

            vlan_id_field = _find_visible_item(
                vlan_page, "labelText", "VLAN ID", "the VLAN ID field"
            )
            _focus_standard_text_field(vlan_id_field)
            _type_text(window, "30")
            _wait_until(
                app,
                lambda: str(vlan_id_field.property("text")) == "30",
                request.timeout_ms,
                "VLAN ID input",
            )
            draft = _to_python(vlan_page.property("draftData")) or {}
            if str(draft.get("vlan_id", "")) != "30" or not bool(
                vlan_id_field.property("inputActiveFocus")
            ):
                raise DocshotError("VLAN ID 30 was not entered through the focused QML field.")
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[3]
                )
            )

            vlan_name_field = _find_visible_item(
                vlan_page, "labelText", "Name", "the VLAN Name field"
            )
            _focus_standard_text_field(vlan_name_field)
            _type_text(window, "Guest")
            _wait_until(
                app,
                lambda: str(vlan_name_field.property("text")) == "Guest",
                request.timeout_ms,
                "VLAN Name input",
            )
            draft = _to_python(vlan_page.property("draftData")) or {}
            if str(draft.get("vlan_id", "")) != "30" or str(
                draft.get("vlan_name", "")
            ) != "Guest":
                raise DocshotError("The VLAN draft does not contain 30 / Guest.")
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[4]
                )
            )

            state_combo = _find_visible_item(
                vlan_page, "labelText", "State", "the VLAN State selector"
            )
            if str(state_combo.property("currentText")) != "active":
                raise DocshotError("The VLAN State selector is not set to active.")
            _click_item(window, state_combo, 0.78)
            _wait_until(
                app,
                lambda: any(
                    "Popup" in candidate.metaObject().className()
                    and bool(candidate.property("visible"))
                    for candidate in window.findChildren(QObject)
                ),
                request.timeout_ms,
                "open VLAN State options",
            )
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[5]
                )
            )

            _send_key(window, Qt.Key.Key_Escape)
            _wait_until(
                app,
                lambda: not any(
                    "Popup" in candidate.metaObject().className()
                    and bool(candidate.property("visible"))
                    for candidate in window.findChildren(QObject)
                ),
                request.timeout_ms,
                "closed VLAN State options",
            )
            draft = _to_python(vlan_page.property("draftData")) or {}
            save_button = _find_visible_named_item(vlan_page, "crudSaveButton")
            if (
                str(draft.get("vlan_id", "")) != "30"
                or str(draft.get("vlan_name", "")) != "Guest"
                or str(draft.get("state", "")) != "active"
                or not save_button.isEnabled()
            ):
                raise DocshotError("The completed VLAN form is not ready to Save.")
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[6]
                )
            )

            _click_item(window, save_button)
            _wait_until(
                app,
                lambda: (
                    int(vlan_page.property("formMode") or 0) == 0
                    and _row_by_vlan(fixture, VLAN_CREATED_ROW[0]) is not None
                ),
                request.timeout_ms,
                "saved VLAN 30 inventory row",
            )
            created = _row_by_vlan(fixture, VLAN_CREATED_ROW[0]) or {}
            if (
                str(created.get("vlan_name", "")) != VLAN_CREATED_ROW[1]
                or str(created.get("state", "")) != VLAN_CREATED_ROW[2]
                or str(created.get("success", "")) != "pending_apply"
                or "saved to the local workspace"
                not in str(vlan_page.property("message")).lower()
            ):
                raise DocshotError("Saved VLAN 30 does not match Guest / active / pending_apply.")

            vlan_30_row = _find_visible_item(
                vlan_page, "rowIndex", 3, "the VLAN 30 inventory row"
            )
            _click_item(window, vlan_30_row)
            _wait_until(
                app,
                lambda: int(vlan_page.property("selectedIndex") or -1) == 3,
                request.timeout_ms,
                "VLAN 30 selection",
            )
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[7]
                )
            )

            preview = fixture.db_manager.previewViewPush(
                "switching", VLAN_FIXTURE_HOST, "vlan"
            )
            commands = str(preview.get("commands", ""))
            if (
                not preview.get("ok")
                or "vlan 30" not in commands
                or " name Guest" not in commands
                or " state active" not in commands
                or "vlan 10" in commands
            ):
                raise DocshotError("The real VLAN preview did not contain only VLAN 30.")

            preview_button = _find_visible_item(
                vlan_page, "moduleName", "vlan", "the VLAN View & Push button"
            )
            _wait_until(
                app,
                preview_button.isEnabled,
                request.timeout_ms,
                "enabled VLAN View & Push button",
            )
            _click_item(window, preview_button)
            _wait_until(
                app,
                lambda: (
                    (
                        panes := [
                            item
                            for item in _visual_items(window)
                            if item.objectName() == "viewPushConfigurationPreview"
                        ]
                    )
                    and "vlan 30" in str(panes[0].property("previewText") or "")
                    and "name Guest" in str(panes[0].property("previewText") or "")
                ),
                request.timeout_ms,
                "VLAN configuration preview dialog",
            )
            staged_paths.append(
                _capture_vlan_step(
                    app, engine, window, request, staging, VLAN_WORKFLOW_FILENAMES[8]
                )
            )

            request.output_dir.mkdir(parents=True, exist_ok=True)
            results: list[RenderResult] = []
            for staged_path, filename in zip(
                staged_paths, VLAN_WORKFLOW_FILENAMES, strict=True
            ):
                destination = request.output_dir / filename
                staged_path.replace(destination)
                _validate_saved_png(destination, request.pixel_size)
                results.append(
                    RenderResult(
                        destination,
                        request.pixel_size.width(),
                        request.pixel_size.height(),
                    )
                )
            return tuple(results)
        finally:
            if window is not None:
                window.close()
                window.deleteLater()
            if engine is not None:
                engine.clearComponentCache()
                engine.deleteLater()
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)


def render_shot(shot: ShotSpec, request: RenderRequest) -> RenderResult:
    if request.width <= 0 or request.height <= 0 or request.scale <= 0:
        raise DocshotError("Width, height, and scale must be greater than zero.")
    app = _application()
    engine: QQmlApplicationEngine | None = None
    window: QQuickWindow | None = None
    with FixtureBundle(request) as fixture:
        try:
            engine = QQmlApplicationEngine()
            engine.addImportPath(str(QML_MODULE_DIR.parent))
            warnings: list[str] = []
            engine.warnings.connect(
                lambda messages: warnings.extend(message.toString() for message in messages)
            )
            context = engine.rootContext()
            for name, value in fixture.context_properties().items():
                context.setContextProperty(name, value)

            engine.loadFromModule("UI", shot.qml_type)
            roots = engine.rootObjects()
            if not roots or not isinstance(roots[-1], QQuickWindow):
                detail = f" QML warnings: {' | '.join(warnings)}" if warnings else ""
                raise DocshotError(f"Could not load UI/{shot.qml_type}.{detail}")
            window = roots[-1]
            _prepare_window(app, engine, window, shot, request)
            image = capture_window(window, request.scale, request.timeout_ms)
            if image.isNull() or image.width() <= 0 or image.height() <= 0:
                raise DocshotError(f"Capture for {shot.name!r} was empty.")
            if image.size() != request.pixel_size:
                raise DocshotError(
                    f"Capture for {shot.name!r} is {image.width()}x{image.height()}, "
                    f"expected {request.pixel_size.width()}x{request.pixel_size.height()}."
                )
            destination = request.output_dir / f"{shot.name}.png"
            _save_png_atomic(image, destination)
            return RenderResult(destination, image.width(), image.height())
        finally:
            if window is not None:
                window.close()
                window.deleteLater()
            if engine is not None:
                engine.clearComponentCache()
                engine.deleteLater()
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)


__all__ = [
    "DocshotError",
    "DocumentationTerminal",
    "FixtureBundle",
    "RenderRequest",
    "RenderResult",
    "VLAN_CREATED_ROW",
    "VLAN_FIXTURE_HOST",
    "VLAN_FIXTURE_ROWS",
    "VLAN_WORKFLOW_FILENAMES",
    "capture_item",
    "capture_window",
    "render_shot",
    "render_vlan_workflow",
]
