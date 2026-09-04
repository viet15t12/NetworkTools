"""Read-only operating-system and desktop-environment detection."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass


GLOBAL_MENU_REGISTRAR = "com.canonical.AppMenu.Registrar"
GLOBAL_MENU_PROBE_TIMEOUT_MS = 300


@dataclass(frozen=True, slots=True)
class DesktopEnvironmentInfo:
    """Normalized platform facts used by presentation policy."""

    platform_family: str
    desktop_family: str
    session_type: str
    qt_platform_plugin: str
    global_menu_registrar_available: bool
    capability_reason: str


def _runtime_qt_platform_plugin() -> str:
    """Return Qt's active platform plugin without requiring an application."""
    try:
        from PyQt6.QtGui import QGuiApplication
    except ImportError:
        return "unknown"
    try:
        application = QGuiApplication.instance()
        if application is None:
            return "unknown"
        return str(application.platformName() or "unknown").casefold()
    except (AttributeError, RuntimeError, TypeError):
        return "unknown"


def detection_failure_info() -> DesktopEnvironmentInfo:
    """Return conservative facts when environment detection cannot complete."""
    return DesktopEnvironmentInfo(
        platform_family="other",
        desktop_family="unknown",
        session_type="unknown",
        qt_platform_plugin="unknown",
        global_menu_registrar_available=False,
        capability_reason="detection-failed",
    )


def _session_bus_has_global_menu_registrar() -> bool:
    """Probe AppMenu with a short bound so desktop startup cannot stall."""
    try:
        from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
    except ImportError:
        return False

    connection = QDBusConnection.sessionBus()
    if not connection.isConnected():
        return False
    interface = QDBusInterface(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        connection,
    )
    if not interface.isValid():
        return False
    interface.setTimeout(GLOBAL_MENU_PROBE_TIMEOUT_MS)
    try:
        reply = interface.call("NameHasOwner", GLOBAL_MENU_REGISTRAR)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            return False
        arguments = reply.arguments()
        return bool(arguments[0]) if arguments else False
    except (AttributeError, RuntimeError, TypeError):
        return False


class DesktopEnvironmentDetector:
    """Detect platform facts with injectable inputs for deterministic tests."""

    def __init__(
        self,
        *,
        platform_id: str | None = None,
        environ: Mapping[str, str] | None = None,
        qt_platform_plugin: str | None = None,
        registrar_probe: Callable[[], bool] | None = None,
    ) -> None:
        self._platform_id = platform_id if platform_id is not None else sys.platform
        self._environ = environ if environ is not None else os.environ
        self._qt_platform_plugin = qt_platform_plugin
        self._registrar_probe = (
            registrar_probe or _session_bus_has_global_menu_registrar
        )

    @staticmethod
    def _platform_family(platform_id: str) -> str:
        value = str(platform_id or "").casefold()
        if value == "darwin":
            return "macos"
        if value.startswith("win"):
            return "windows"
        if value.startswith("linux"):
            return "linux"
        return "other"

    def _desktop_tokens(self) -> set[str]:
        values = (
            self._environ.get("XDG_CURRENT_DESKTOP", ""),
            self._environ.get("XDG_SESSION_DESKTOP", ""),
            self._environ.get("DESKTOP_SESSION", ""),
        )
        tokens: set[str] = set()
        for value in values:
            tokens.update(
                token
                for token in re.split(r"[:;,/\s]+", str(value or "").casefold())
                if token
            )
        if self._environ.get("KDE_FULL_SESSION", "").casefold() in {
            "1",
            "true",
            "yes",
        }:
            tokens.add("kde")
        if self._environ.get("GNOME_DESKTOP_SESSION_ID", ""):
            tokens.add("gnome")
        return tokens

    def _desktop_family(self, platform_family: str) -> str:
        if platform_family != "linux":
            return "none"
        tokens = self._desktop_tokens()
        if tokens.intersection({"kde", "plasma", "plasmawayland", "plasma-x11"}):
            return "kde"
        if "unity" in tokens:
            return "unity"
        if tokens.intersection(
            {"gnome", "ubuntu", "cinnamon", "budgie", "mate", "pop"}
        ):
            return "gnome"
        return "other" if tokens else "unknown"

    def _session_type(self, platform_family: str) -> str:
        if platform_family == "windows":
            return "windows"
        if platform_family == "macos":
            return "cocoa"
        value = self._environ.get("XDG_SESSION_TYPE", "").strip().casefold()
        return value if value in {"wayland", "x11"} else "unknown"

    def detect(self) -> DesktopEnvironmentInfo:
        platform_family = self._platform_family(self._platform_id)
        desktop_family = self._desktop_family(platform_family)
        session_type = self._session_type(platform_family)
        qt_platform_plugin = (
            str(self._qt_platform_plugin).casefold()
            if self._qt_platform_plugin is not None
            else _runtime_qt_platform_plugin()
        )

        registrar_available = False
        if platform_family == "linux":
            try:
                registrar_available = bool(self._registrar_probe())
            except Exception:
                registrar_available = False

        if platform_family == "macos":
            capability_reason = "macos-system-menu"
        elif platform_family == "linux" and registrar_available:
            capability_reason = "dbus-registrar-present"
        elif platform_family == "linux":
            capability_reason = "dbus-registrar-missing"
        else:
            capability_reason = "unsupported-platform"

        return DesktopEnvironmentInfo(
            platform_family=platform_family,
            desktop_family=desktop_family,
            session_type=session_type,
            qt_platform_plugin=qt_platform_plugin,
            global_menu_registrar_available=registrar_available,
            capability_reason=capability_reason,
        )


__all__ = [
    "GLOBAL_MENU_REGISTRAR",
    "GLOBAL_MENU_PROBE_TIMEOUT_MS",
    "DesktopEnvironmentDetector",
    "DesktopEnvironmentInfo",
    "detection_failure_info",
]
