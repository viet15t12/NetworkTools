from __future__ import annotations

import ctypes
import importlib.util
import os
import signal
import sys
from pathlib import Path


_QT_DLL_DIRECTORY_HANDLES: list[object] = []
_QT_LIBRARY_HANDLES: list[object] = []
_QT_LABS_PLATFORM_REGISTERED = False
APP_USER_MODEL_ID = "NetCamsTeam.CAMS.App"
APP_DESKTOP_FILE_NAME = "cams"
RUNTIME_QML_DIR = Path(__file__).resolve().parent / "runtime_qml"


def _prepend_env_path(name: str, value: Path) -> None:
    current = os.environ.get(name)
    value_text = str(value)
    if current:
        paths = current.split(os.pathsep)
        if value_text in paths:
            return
        os.environ[name] = f"{value_text}{os.pathsep}{current}"
    else:
        os.environ[name] = value_text


def _configure_qt_logging() -> None:
    """Silence a known Qt Wayland text-input diagnostic without hiding other logs."""
    if not sys.platform.startswith("linux"):
        return
    session_type = os.environ.get("XDG_SESSION_TYPE", "").casefold()
    qt_platform = os.environ.get("QT_QPA_PLATFORM", "").casefold()
    if "wayland" not in session_type and "wayland" not in qt_platform:
        return

    category = "qt.qpa.wayland.textinput"
    rules = os.environ.get("QT_LOGGING_RULES", "")
    split_rules = rules.replace("\n", ";").split(";")
    if any(rule.strip().startswith(f"{category}=") for rule in split_rules):
        return
    os.environ["QT_LOGGING_RULES"] = f"{rules + ';' if rules else ''}{category}=false"


def _bootstrap_pyqt6_paths() -> None:
    spec = importlib.util.find_spec("PyQt6")
    if spec is None or spec.submodule_search_locations is None:
        return

    pyqt6_dir = Path(next(iter(spec.submodule_search_locations)))
    qt6_dir = pyqt6_dir / "Qt6"
    qt_bin_dir = qt6_dir / "bin"
    qt_plugins_dir = qt6_dir / "plugins"
    qt_platforms_dir = qt_plugins_dir / "platforms"
    qt_qml_dir = qt6_dir / "qml"

    if os.name == "nt" and qt_bin_dir.exists():
        _QT_DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(qt_bin_dir)))
        _prepend_env_path("PATH", qt_bin_dir)
    if qt_plugins_dir.exists():
        _prepend_env_path("QT_PLUGIN_PATH", qt_plugins_dir)
    if qt_platforms_dir.exists():
        _prepend_env_path("QT_QPA_PLATFORM_PLUGIN_PATH", qt_platforms_dir)
    if qt_qml_dir.exists():
        _prepend_env_path("QML2_IMPORT_PATH", qt_qml_dir)

    labs_platform_module = qt_qml_dir / "Qt" / "labs" / "platform"
    if not labs_platform_module.exists() and RUNTIME_QML_DIR.exists():
        # PyQt's Qt runtime contains Qt6LabsPlatform, but some wheels omit its
        # tiny QML plugin directory. Register the matching bundled library and
        # use our qmldir shim; never mix it with a system Qt of another version.
        if _register_bundled_qt_labs_platform(qt6_dir):
            _prepend_env_path("QML2_IMPORT_PATH", RUNTIME_QML_DIR)


def _register_bundled_qt_labs_platform(qt6_dir: Path) -> bool:
    """Register Qt Labs Platform when a PyQt wheel omits its QML plugin."""
    global _QT_LABS_PLATFORM_REGISTERED
    if _QT_LABS_PLATFORM_REGISTERED:
        return True

    library_candidates = (
        qt6_dir / "lib" / "libQt6LabsPlatform.so.6",
        qt6_dir / "lib" / "libQt6LabsPlatform.dylib",
        qt6_dir / "bin" / "Qt6LabsPlatform.dll",
    )
    symbol_candidates = (
        "_Z35qml_register_types_Qt_labs_platformv",
        "?qml_register_types_Qt_labs_platform@@YAXXZ",
        "qml_register_types_Qt_labs_platform",
    )

    library_path = next(
        (path for path in library_candidates if path.is_file()), None
    )
    if library_path is None:
        return False
    try:
        library = ctypes.CDLL(str(library_path))
        register = next(
            (
                getattr(library, symbol)
                for symbol in symbol_candidates
                if hasattr(library, symbol)
            ),
            None,
        )
        if register is None:
            return False
        register.argtypes = []
        register.restype = None
        register()
        _QT_LIBRARY_HANDLES.append(library)
        _QT_LABS_PLATFORM_REGISTERED = True
        return True
    except (AttributeError, OSError):
        return False


def _set_windows_app_user_model_id() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


_configure_qt_logging()
_bootstrap_pyqt6_paths()

from PyQt6.QtCore import QMetaObject
from PyQt6.QtGui import QIcon
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtWidgets import QApplication

from app_facade import (
    AppPaths,
    DatabaseManager,
    ExternalToolsManager,
    LanguageSettings,
    MenuPresentationController,
    NetworkMonitor,
    QML_MODULE_DIR,
    StatusBarSettings,
    SystemAppearance,
    TerminalHelper,
    ThemeSettings,
    WindowSettings,
    WelcomeController,
    WorkspaceSaveController,
)
from scripts.build_databases import ensure_runtime_databases
from features.config_backup import ConfigBackupService
from features.config_sync import ConfigSyncService
from features.devices import DeviceLoginService, DeviceRepository, DeviceService
from features.sftp import SftpController
from features.syslog import SyslogManager
from infrastructure.network.session_registry import DeviceSessionRegistry
from infrastructure.database.paths import DEVICE_NETWORK_DB, INFO_COLLECTED_DB
from infrastructure.system.runtime_tmp import cleanup_runtime_tmp


def _runtime_arguments(argv: list[str]) -> tuple[list[str], str]:
    """Remove private brand flags and return the last selected Easter Egg."""
    brand_flags = {"-v": "nqv", "--nqv": "nqv", "-p": "ptit", "--ptit": "ptit"}
    brand_mode = ""
    for argument in argv[1:]:
        if argument in brand_flags:
            brand_mode = brand_flags[argument]
    qt_arguments = [
        argument for index, argument in enumerate(argv)
        if index == 0 or argument not in brand_flags
    ]
    return qt_arguments, brand_mode


def _application_icon_path(platform_name: str | None = None) -> Path:
    """Return an icon format that Qt and the host desktop render reliably."""
    platform_name = platform_name or sys.platform
    suffix = "ico" if platform_name.startswith("win") else "png"
    return QML_MODULE_DIR / "resources" / "brand" / f"logo.{suffix}"


def main() -> int:
    _set_windows_app_user_model_id()
    qt_arguments, brand_easter_egg = _runtime_arguments(sys.argv)
    try:
        bootstrap_report = ensure_runtime_databases()
    except Exception as exc:
        print(f"Failed to create missing databases: {exc}", file=sys.stderr)
        return 1

    app = QApplication(qt_arguments)
    app.setOrganizationName("NetCamsTeam")
    app.setOrganizationDomain("ptit.edu.vn")
    app.setApplicationName("CAMS")
    if sys.platform.startswith("linux"):
        # Match packaging/linux's cams.desktop so Wayland associates the
        # running window with the launcher and displays its icon correctly.
        app.setDesktopFileName(APP_DESKTOP_FILE_NAME)

    icon_path = _application_icon_path()
    application_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not application_icon.isNull():
        app.setWindowIcon(application_icon)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(Path(__file__).resolve().parent))
    engine.warnings.connect(lambda warnings: [print(w.toString(), file=sys.stderr) for w in warnings])

    default_backup_root = Path(__file__).resolve().parent / "backup"
    config_backup_service = ConfigBackupService(default_backup_root)
    device_repository = DeviceRepository()
    # A previous unclean exit may leave process-local connection state behind.
    device_repository.activate_database(DEVICE_NETWORK_DB)
    config_sync_service = ConfigSyncService(DEVICE_NETWORK_DB, device_repository.get_role)
    device_login_service = DeviceLoginService(device_repository)
    device_service = DeviceService(device_repository)
    session_registry = DeviceSessionRegistry(device_login_service.load)
    db_manager = DatabaseManager(
        config_backup_service=config_backup_service,
        session_registry=session_registry,
        config_sync_service=config_sync_service,
    )
    cli = TerminalHelper(
        config_backup_service=config_backup_service,
        config_sync_service=config_sync_service,
        session_registry=session_registry,
        injected_device_service=device_service,
        injected_login_service=device_login_service,
        bootstrap_report=bootstrap_report,
    )
    status_bar_settings = StatusBarSettings()
    network_monitor = NetworkMonitor(settings=status_bar_settings)
    theme_settings = ThemeSettings()
    menu_presentation = MenuPresentationController()
    language_settings = LanguageSettings()
    system_appearance = SystemAppearance()
    window_settings = WindowSettings()
    welcome_controller = WelcomeController()

    def prepare_workspace_close() -> None:
        """Disconnect devices and persist their offline state before packaging."""
        # This callback runs on the workspace writer thread, so a slow network
        # disconnect never blocks QML. Unlike application shutdown, an explicit
        # workspace close waits for every disconnect before rebuilding .ntp.
        session_registry.close_all(timeout=None)
        device_repository.reset_connected_to_waiting()

    workspace_save_controller = WorkspaceSaveController(
        welcome_controller,
        workspace_close_preparer=prepare_workspace_close,
    )
    app_paths = AppPaths()
    external_tools = ExternalToolsManager()
    # NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
    sftp_controller = SftpController(device_login_service=device_login_service)
    # Syslog owns its own threads/database boundary.
    syslog_manager = SyslogManager()
    shutdown_complete = False

    def route_active_workspace() -> None:
        """Keep runtime services on the databases extracted from the active project."""
        if shutdown_complete:
            return
        session = welcome_controller.active_session()
        if session is None:
            # closeProject() emits this signal before removing its extracted
            # directory. Drop every database reference first so Windows does
            # not retain locks that prevent temporary-workspace cleanup.
            if not db_manager.set_workspace_databases(
                DEVICE_NETWORK_DB, INFO_COLLECTED_DB
            ):
                print("Failed to restore the default application databases.", file=sys.stderr)
                return
            device_repository.activate_database(DEVICE_NETWORK_DB)
            config_sync_service.db_path = str(DEVICE_NETWORK_DB)
            config_backup_service.repository.backup_root = default_backup_root
            external_tools.device_db_path = DEVICE_NETWORK_DB
            syslog_manager.set_database_paths(
                INFO_COLLECTED_DB, DEVICE_NETWORK_DB
            )
            return
        if not db_manager.set_workspace_databases(
            session.device_network_db, session.info_collected_db
        ):
            print("Failed to activate the workspace databases.", file=sys.stderr)
            return
        # The package may contain a stale `connected` value from an earlier app
        # run. No session exists in this process until the user connects again.
        device_repository.activate_database(session.device_network_db)
        config_sync_service.db_path = str(session.device_network_db)
        config_backup_service.repository.backup_root = session.backup_directory
        external_tools.device_db_path = session.device_network_db
        syslog_manager.set_database_paths(
            session.info_collected_db, session.device_network_db
        )
        if syslog_manager.settings.enabledOnStartup \
                and syslog_manager.listenerState == "stopped":
            result = syslog_manager.startServer()
            if not result["ok"]:
                print(f"Syslog auto-start failed: {result['message']}", file=sys.stderr)

    welcome_controller.activeWorkspaceChanged.connect(route_active_workspace)

    def shutdown() -> None:
        nonlocal shutdown_complete
        if shutdown_complete:
            return
        shutdown_complete = True
        try:
            # Stop new callbacks/tasks first, then abort network I/O before releasing sessions.
            network_monitor.shutdown()
            db_manager.shutdown()
            cli.shutdown()
            try:
                repository_path = Path(device_repository.db_path)
                if repository_path.is_file():
                    device_repository.reset_connected_to_waiting()
            except Exception as exc:
                print(f"Failed to reset connected devices during shutdown: {exc}", file=sys.stderr)
            syslog_manager.shutdown()
            sftp_controller.shutdown()
            workspace_save_controller.shutdown()
            welcome_controller.shutdown()
        finally:
            for cleanup_error in cleanup_runtime_tmp():
                print(
                    f"Failed to remove temporary runtime artifact: {cleanup_error}",
                    file=sys.stderr,
                )

    app.aboutToQuit.connect(shutdown)

    context = engine.rootContext()
    context.setContextProperty("dbManager", db_manager)
    context.setContextProperty("cli", cli)
    context.setContextProperty("networkMonitor", network_monitor)
    context.setContextProperty("statusBarSettings", status_bar_settings)
    context.setContextProperty("themeSettings", theme_settings)
    context.setContextProperty("languageSettings", language_settings)
    context.setContextProperty("menuPresentation", menu_presentation)
    context.setContextProperty("systemAppearance", system_appearance)
    context.setContextProperty("windowSettings", window_settings)
    context.setContextProperty("welcomeController", welcome_controller)
    context.setContextProperty("workspaceSaveController", workspace_save_controller)
    context.setContextProperty("AppPaths", app_paths)
    context.setContextProperty("externalTools", external_tools)
    context.setContextProperty("sftpController", sftp_controller)
    context.setContextProperty("syslogManager", syslog_manager)
    context.setContextProperty("syslogSettings", syslog_manager.settings)
    context.setContextProperty("nqvEasterEggEnabled", brand_easter_egg == "nqv")
    context.setContextProperty("ptitEasterEggEnabled", brand_easter_egg == "ptit")

    workspace_window: object | None = None
    welcome_window: object | None = None

    def hide_window_safely(window: object | None) -> None:
        """Release text-input focus before hiding a Wayland surface."""
        if window is None or not window.isVisible():
            return
        QMetaObject.invokeMethod(window, "prepareForWindowHide")
        input_method = app.inputMethod()
        input_method.commit()
        input_method.reset()
        window.hide()

    def open_workspace(project_name: str, project_path: str) -> None:
        nonlocal workspace_window
        hide_window_safely(welcome_window)
        if workspace_window is None:
            existing_roots = set(engine.rootObjects())
            engine.loadFromModule("UI", "Main")
            created_roots = [
                root for root in engine.rootObjects() if root not in existing_roots
            ]
            if not created_roots:
                print("Failed to load QML module UI/Main.", file=sys.stderr)
                if welcome_window is not None:
                    welcome_window.show()
                return
            workspace_window = created_roots[-1]
            if not application_icon.isNull():
                workspace_window.setIcon(application_icon)

        workspace_window.setProperty("workspaceDisplayName", project_name)
        workspace_window.setProperty("workspacePath", project_path)
        workspace_window.show()
        workspace_window.raise_()
        workspace_window.requestActivate()

    def show_welcome(mode: str) -> None:
        if welcome_window is None:
            return
        hide_window_safely(workspace_window)
        welcome_window.show()
        welcome_window.raise_()
        welcome_window.requestActivate()
        if mode:
            welcome_window.setProperty("requestedMode", mode)

    welcome_controller.workspaceRequested.connect(open_workspace)
    welcome_controller.welcomeRequested.connect(show_welcome)

    engine.loadFromModule("UI", "Welcome")
    if not engine.rootObjects():
        print("Failed to load QML module UI/Welcome.", file=sys.stderr)
        return 1
    welcome_window = engine.rootObjects()[0]
    if not application_icon.isNull():
        welcome_window.setIcon(application_icon)

    def request_shutdown(_signum: int, _frame: object) -> None:
        app.quit()

    console_signals = [signal.SIGINT]
    if hasattr(signal, "SIGBREAK"):
        console_signals.append(signal.SIGBREAK)
    previous_signal_handlers = {
        console_signal: signal.getsignal(console_signal) for console_signal in console_signals
    }
    for console_signal in console_signals:
        signal.signal(console_signal, request_shutdown)
    try:
        return app.exec()
    except KeyboardInterrupt:
        # Defensive fallback for platforms that raise before the SIGINT handler is installed.
        return 0
    finally:
        shutdown()
        for console_signal, previous_handler in previous_signal_handlers.items():
            signal.signal(console_signal, previous_handler)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0) from None
