"""Compatibility imports; remove after 2026-10-20 once external consumers migrate."""

from infrastructure.database.paths import DEVICE_NETWORK_DB as DB_PATH
from infrastructure.database.paths import DEVICE_NETWORK_SQL as SQL_PATH

from .app_paths import APP_DIR, FEATURES_DIR, QML_MODULE_DIR, AppPaths
from .external_tools import ExternalToolsManager
from .localization import LanguageSettings
from .monitoring import NetworkMonitor
from .settings import StatusBarSettings, ThemeSettings, WindowSettings
from .terminal import TerminalHelper, device_session_registry

__all__ = [
    "APP_DIR", "FEATURES_DIR", "DB_PATH", "ExternalToolsManager", "QML_MODULE_DIR",
    "SQL_PATH", "AppPaths", "LanguageSettings", "NetworkMonitor", "StatusBarSettings", "TerminalHelper",
    "ThemeSettings", "WindowSettings", "device_session_registry",
]
