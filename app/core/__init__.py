"""Public core API with lazy imports to keep feature modules independently testable."""

from __future__ import annotations

from typing import Any

from .app_paths import APP_DIR, FEATURES_DIR, QML_MODULE_DIR, AppPaths
from infrastructure.database.paths import (
    DEVICE_NETWORK_DB as DB_PATH,
    DEVICE_NETWORK_SQL as SQL_PATH,
)

_LAZY_EXPORTS = {
    "DatabaseManager": (".database", "DatabaseManager"),
    "LanguageSettings": (".localization", "LanguageSettings"),
    "MenuPresentationController": (".menu_presentation", "MenuPresentationController"),
    "NetworkMonitor": (".monitoring", "NetworkMonitor"),
    "StatusBarSettings": (".settings", "StatusBarSettings"),
    "TerminalHelper": (".terminal", "TerminalHelper"),
}


def __getattr__(name: str) -> Any:
    """Load heavy runtime facades only when a caller explicitly requests one."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


__all__ = [
    "APP_DIR",
    "FEATURES_DIR",
    "DB_PATH",
    "QML_MODULE_DIR",
    "SQL_PATH",
    "AppPaths",
    "DatabaseManager",
    "LanguageSettings",
    "MenuPresentationController",
    "NetworkMonitor",
    "StatusBarSettings",
    "TerminalHelper",
]
