"""Persistent QSettings-backed QML objects."""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QFileSystemWatcher,
    QObject,
    QSettings,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QGuiApplication


class SystemAppearance(QObject):
    """Expose a reliable, live light/dark preference to QML."""

    appearanceChanged = pyqtSignal()

    LIGHT = 1
    DARK = 2

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        poll_interval_ms: int = 5000,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = self.LIGHT
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._configuration_changed)
        self._watcher.directoryChanged.connect(self._configuration_changed)

        application = QGuiApplication.instance()
        self._style_hints = (
            application.styleHints()
            if isinstance(application, QGuiApplication)
            else None
        )
        if self._style_hints is not None:
            color_scheme_changed = getattr(
                self._style_hints,
                "colorSchemeChanged",
                None,
            )
            if color_scheme_changed is not None:
                color_scheme_changed.connect(self.refresh)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(max(1000, int(poll_interval_ms)))
        self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start()
        self._refresh_watched_paths()
        self.refresh()

    def _configuration_paths(self) -> list[Path]:
        config_home = Path(
            os.environ.get("XDG_CONFIG_HOME")
            or (Path.home() / ".config")
        )
        return [
            config_home / "dconf" / "user",
            config_home / "gtk-3.0" / "settings.ini",
            config_home / "gtk-4.0" / "settings.ini",
            config_home / "kdeglobals",
        ]

    def _refresh_watched_paths(self) -> None:
        watched = set(self._watcher.files())
        for path in self._configuration_paths():
            text = str(path)
            if path.is_file() and text not in watched:
                self._watcher.addPath(text)

    def _configuration_changed(self, _path: str) -> None:
        self._refresh_watched_paths()
        self.refresh()

    def _portal_color_scheme(self) -> int | None:
        try:
            from PyQt6.QtDBus import (
                QDBusConnection,
                QDBusInterface,
                QDBusMessage,
            )
        except ImportError:
            return None
        connection = QDBusConnection.sessionBus()
        if not connection.isConnected():
            return None
        interface = QDBusInterface(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings",
            connection,
        )
        if not interface.isValid():
            return None
        interface.setTimeout(1000)
        reply = interface.call(
            "Read",
            "org.freedesktop.appearance",
            "color-scheme",
        )
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            return None
        arguments = reply.arguments()
        if not arguments:
            return None
        value: Any = arguments[0]
        if hasattr(value, "variant"):
            value = value.variant()
        try:
            preference = int(value)
        except (TypeError, ValueError):
            return None
        if preference == 1:
            return self.DARK
        if preference == 2:
            return self.LIGHT
        return None

    def _gsettings_color_scheme(self) -> int | None:
        executable = shutil.which("gsettings")
        if not executable:
            return None
        try:
            result = subprocess.run(
                [
                    executable,
                    "get",
                    "org.gnome.desktop.interface",
                    "color-scheme",
                ],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip().strip("'\"").casefold()
        if value == "prefer-dark":
            return self.DARK
        if value in {"default", "prefer-light"}:
            return self.LIGHT
        return None

    def _gtk_color_scheme(self) -> int | None:
        gtk_theme = os.environ.get("GTK_THEME", "").casefold()
        if gtk_theme:
            return self.DARK if "dark" in gtk_theme else self.LIGHT
        for path in self._configuration_paths():
            if path.name != "settings.ini" or not path.is_file():
                continue
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read(path, encoding="utf-8")
            except (OSError, configparser.Error):
                continue
            section = "Settings"
            if not parser.has_section(section):
                continue
            preference = parser.get(
                section,
                "gtk-application-prefer-dark-theme",
                fallback="",
            ).strip().casefold()
            if preference in {"1", "true", "yes", "on"}:
                return self.DARK
            theme_name = parser.get(
                section,
                "gtk-theme-name",
                fallback="",
            ).casefold()
            if theme_name:
                return self.DARK if "dark" in theme_name else self.LIGHT
        return None

    def _kde_color_scheme(self) -> int | None:
        kdeglobals = next(
            (
                path
                for path in self._configuration_paths()
                if path.name == "kdeglobals" and path.is_file()
            ),
            None,
        )
        if kdeglobals is None:
            return None
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(kdeglobals, encoding="utf-8")
        except (OSError, configparser.Error):
            return None
        color_scheme = parser.get("KDE", "ColorScheme", fallback="").casefold()
        if color_scheme and any(
            marker in color_scheme
            for marker in ("dark", "black")
        ):
            return self.DARK
        background = parser.get(
            "Colors:Window",
            "BackgroundNormal",
            fallback="",
        )
        try:
            red, green, blue = (
                int(channel.strip())
                for channel in background.split(",")[:3]
            )
        except (TypeError, ValueError):
            return None
        luminance = (
            0.2126 * red
            + 0.7152 * green
            + 0.0722 * blue
        ) / 255
        return self.DARK if luminance < 0.5 else self.LIGHT

    def _qt_color_scheme(self) -> int | None:
        if self._style_hints is None:
            return None
        scheme = self._style_hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return self.DARK
        if scheme == Qt.ColorScheme.Light:
            return self.LIGHT
        return None

    def _palette_color_scheme(self) -> int:
        application = QGuiApplication.instance()
        if not isinstance(application, QGuiApplication):
            return self.LIGHT
        color = application.palette().window().color()
        luminance = (
            0.2126 * color.redF()
            + 0.7152 * color.greenF()
            + 0.0722 * color.blueF()
        )
        return self.DARK if luminance < 0.5 else self.LIGHT

    def _detect_color_scheme(self) -> int:
        if sys.platform.startswith("linux"):
            desktop = " ".join((
                os.environ.get("XDG_CURRENT_DESKTOP", ""),
                os.environ.get("XDG_SESSION_DESKTOP", ""),
                os.environ.get("DESKTOP_SESSION", ""),
            )).casefold()
            if "kde" in desktop or "plasma" in desktop:
                desktop_detectors = (
                    self._kde_color_scheme,
                    self._gtk_color_scheme,
                    self._gsettings_color_scheme,
                )
            elif any(
                name in desktop
                for name in ("gnome", "cinnamon", "budgie", "mate")
            ):
                desktop_detectors = (
                    self._gsettings_color_scheme,
                    self._gtk_color_scheme,
                    self._kde_color_scheme,
                )
            else:
                desktop_detectors = (
                    self._gtk_color_scheme,
                    self._kde_color_scheme,
                    self._gsettings_color_scheme,
                )
            for detector in (
                self._portal_color_scheme,
                *desktop_detectors,
            ):
                scheme = detector()
                if scheme is not None:
                    return scheme
        return self._qt_color_scheme() or self._palette_color_scheme()

    @pyqtSlot()
    def refresh(self) -> None:
        self._refresh_watched_paths()
        color_scheme = self._detect_color_scheme()
        if color_scheme == self._color_scheme:
            return
        self._color_scheme = color_scheme
        self.appearanceChanged.emit()

    @pyqtProperty(int, notify=appearanceChanged)
    def colorScheme(self) -> int:
        return self._color_scheme

    @pyqtProperty(bool, notify=appearanceChanged)
    def prefersDark(self) -> bool:
        return self._color_scheme == self.DARK


class WindowSettings(QObject):
    """Persist main-window geometry without depending on optional QML plugins."""

    settingsChanged = pyqtSignal()

    DEFAULTS: dict[str, Any] = {
        "savedX": 0,
        "savedY": 0,
        "savedWidth": 1280,
        "savedHeight": 800,
        "isMaximized": True,
        "isFirstLaunch": True,
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        settings = QSettings()
        self._settings = settings
        self._values = {
            key: settings.value(f"Window/{key}", default, type=type(default))
            for key, default in self.DEFAULTS.items()
        }

    @pyqtSlot(int, int, int, int, bool)
    def saveState(self, x: int, y: int, width: int, height: int, is_maximized: bool) -> None:
        updates = {
            "savedX": int(x),
            "savedY": int(y),
            "savedWidth": max(1, int(width)),
            "savedHeight": max(1, int(height)),
            "isMaximized": bool(is_maximized),
            "isFirstLaunch": False,
        }
        self._values.update(updates)
        for key, value in updates.items():
            self._settings.setValue(f"Window/{key}", value)
        self._settings.sync()
        self.settingsChanged.emit()

    @pyqtSlot()
    def markLaunched(self) -> None:
        if not bool(self._values["isFirstLaunch"]):
            return
        self._values["isFirstLaunch"] = False
        self._settings.setValue("Window/isFirstLaunch", False)
        self._settings.sync()
        self.settingsChanged.emit()

    @pyqtProperty(int, notify=settingsChanged)
    def savedX(self) -> int:
        return int(self._values["savedX"])

    @pyqtProperty(int, notify=settingsChanged)
    def savedY(self) -> int:
        return int(self._values["savedY"])

    @pyqtProperty(int, notify=settingsChanged)
    def savedWidth(self) -> int:
        return int(self._values["savedWidth"])

    @pyqtProperty(int, notify=settingsChanged)
    def savedHeight(self) -> int:
        return int(self._values["savedHeight"])

    @pyqtProperty(bool, notify=settingsChanged)
    def isMaximized(self) -> bool:
        return bool(self._values["isMaximized"])

    @pyqtProperty(bool, notify=settingsChanged)
    def isFirstLaunch(self) -> bool:
        return bool(self._values["isFirstLaunch"])


class ThemeSettings(QObject):
    settingsChanged = pyqtSignal()

    DEFAULTS: dict[str, Any] = {
        "themeMode": 0,
        "highContrast": False,
        "accentColorIndex": 4,
        "lightDarkSideBar": False,
        "useSystemAccentColor": False,
        "useCustomAccentColor": False,
        "customAccentColor": "#356FD6",
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings()
        legacy_theme_mode = self._settings.value("Theme/themeMode", self.DEFAULTS["themeMode"])
        try:
            legacy_theme_mode = int(legacy_theme_mode)
        except (TypeError, ValueError):
            legacy_theme_mode = self.DEFAULTS["themeMode"]
        self._values: dict[str, Any] = {
            key: self._read_value(key, default)
            for key, default in self.DEFAULTS.items()
        }
        if legacy_theme_mode in {3, 4}:
            self._values["themeMode"] = 1 if legacy_theme_mode == 3 else 2
            self._values["highContrast"] = True
            self._settings.setValue("Theme/themeMode", self._values["themeMode"])
            self._settings.setValue("Theme/highContrast", True)
            self._settings.sync()

    def _read_value(self, key: str, default: Any) -> Any:
        value_type = type(default)
        try:
            value = self._settings.value(f"Theme/{key}", default, type=value_type)
        except TypeError:
            value = self._settings.value(f"Theme/{key}", default)
        return self._normalize_value(key, value)

    def _normalize_value(self, key: str, value: Any) -> Any:
        if key == "themeMode":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return self.DEFAULTS[key]
            return value if value in {0, 1, 2} else self.DEFAULTS[key]
        if key == "accentColorIndex":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return self.DEFAULTS[key]
            return value if 0 <= value <= 11 else self.DEFAULTS[key]
        if key in {
            "highContrast",
            "lightDarkSideBar",
            "useSystemAccentColor",
            "useCustomAccentColor",
        }:
            if isinstance(value, str):
                return value.strip().casefold() in {"1", "true", "yes", "on"}
            return bool(value)
        if key == "customAccentColor":
            value = str(value or "").strip()
            return value if value else self.DEFAULTS[key]
        return value

    def _set_value(self, key: str, value: Any) -> None:
        value = self._normalize_value(key, value)
        if self._values.get(key) == value:
            return

        self._values[key] = value
        self._settings.setValue(f"Theme/{key}", value)
        self._settings.sync()
        self.settingsChanged.emit()

    @pyqtProperty(int, notify=settingsChanged)
    def themeMode(self) -> int:
        return int(self._values["themeMode"])

    @themeMode.setter
    def themeMode(self, value: int) -> None:
        self._set_value("themeMode", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def highContrast(self) -> bool:
        return bool(self._values["highContrast"])

    @highContrast.setter
    def highContrast(self, value: bool) -> None:
        self._set_value("highContrast", value)

    @pyqtProperty(int, notify=settingsChanged)
    def accentColorIndex(self) -> int:
        return int(self._values["accentColorIndex"])

    @accentColorIndex.setter
    def accentColorIndex(self, value: int) -> None:
        self._set_value("accentColorIndex", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def lightDarkSideBar(self) -> bool:
        return bool(self._values["lightDarkSideBar"])

    @lightDarkSideBar.setter
    def lightDarkSideBar(self, value: bool) -> None:
        self._set_value("lightDarkSideBar", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def useSystemAccentColor(self) -> bool:
        return bool(self._values["useSystemAccentColor"])

    @useSystemAccentColor.setter
    def useSystemAccentColor(self, value: bool) -> None:
        self._set_value("useSystemAccentColor", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def useCustomAccentColor(self) -> bool:
        return bool(self._values["useCustomAccentColor"])

    @useCustomAccentColor.setter
    def useCustomAccentColor(self, value: bool) -> None:
        self._set_value("useCustomAccentColor", value)

    @pyqtProperty(str, notify=settingsChanged)
    def customAccentColor(self) -> str:
        return str(self._values["customAccentColor"])

    @customAccentColor.setter
    def customAccentColor(self, value: str) -> None:
        self._set_value("customAccentColor", value)


class StatusBarSettings(QObject):
    settingsChanged = pyqtSignal()

    DEFAULTS: dict[str, Any] = {
        "showStatusBar": True,
        "showPythonStatus": True,
        "showNetwork": True,
        "showNetworkName": True,
        "virtualLabServerUrl": "",
        "virtualLabUsername": "",
        "virtualLabPassword": "",
        "showRam": True,
        "showRamBar": True,
        "showRamText": True,
        "ramWarningEnabled": True,
        "ramBlinkOnHigh": True,
        "ramWarningThreshold": 85,
        "showDate": True,
        "showTime": True,
        "showNotifications": True,
        "dateTimeFormatMode": 0,
        "customDateFormat": "dd/MM/yyyy",
        "customTimeFormat": "HH:mm",
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings()
        self._values: dict[str, Any] = {
            key: ("" if key == "virtualLabPassword" else self._read_value(key, default))
            for key, default in self.DEFAULTS.items()
        }
        # API passwords are session-only; discard values from older builds that
        # may have persisted this field in the application settings.
        self._settings.remove("StatusBar/virtualLabPassword")

    def _read_value(self, key: str, default: Any) -> Any:
        value_type = type(default)
        try:
            return self._settings.value(f"StatusBar/{key}", default, type=value_type)
        except TypeError:
            return self._settings.value(f"StatusBar/{key}", default)

    def _set_value(self, key: str, value: Any) -> None:
        default = self.DEFAULTS[key]
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            value = int(value)
        else:
            value = str(value)

        if key == "ramWarningThreshold":
            value = max(1, min(100, value))
        elif key == "dateTimeFormatMode":
            value = 1 if value == 1 else 0

        if self._values.get(key) == value:
            return

        self._values[key] = value
        if key == "virtualLabPassword":
            self.settingsChanged.emit()
            return
        self._settings.setValue(f"StatusBar/{key}", value)
        self._settings.sync()
        self.settingsChanged.emit()

    @pyqtSlot()
    def resetDefaults(self) -> None:
        changed = False
        for key, default in self.DEFAULTS.items():
            if self._values.get(key) != default:
                self._values[key] = default
                if key == "virtualLabPassword":
                    self._settings.remove("StatusBar/virtualLabPassword")
                else:
                    self._settings.setValue(f"StatusBar/{key}", default)
                changed = True
        if changed:
            self._settings.sync()
            self.settingsChanged.emit()

    @pyqtProperty(bool, notify=settingsChanged)
    def showStatusBar(self) -> bool:
        return bool(self._values["showStatusBar"])

    @showStatusBar.setter
    def showStatusBar(self, value: bool) -> None:
        self._set_value("showStatusBar", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showPythonStatus(self) -> bool:
        return bool(self._values["showPythonStatus"])

    @showPythonStatus.setter
    def showPythonStatus(self, value: bool) -> None:
        self._set_value("showPythonStatus", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showNetwork(self) -> bool:
        return bool(self._values["showNetwork"])

    @showNetwork.setter
    def showNetwork(self, value: bool) -> None:
        self._set_value("showNetwork", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showNetworkName(self) -> bool:
        return bool(self._values["showNetworkName"])

    @showNetworkName.setter
    def showNetworkName(self, value: bool) -> None:
        self._set_value("showNetworkName", value)

    @pyqtProperty(str, notify=settingsChanged)
    def virtualLabServerUrl(self) -> str:
        return str(self._values["virtualLabServerUrl"])

    @virtualLabServerUrl.setter
    def virtualLabServerUrl(self, value: str) -> None:
        self._set_value("virtualLabServerUrl", value.strip())

    @pyqtProperty(str, notify=settingsChanged)
    def virtualLabUsername(self) -> str:
        return str(self._values["virtualLabUsername"])

    @virtualLabUsername.setter
    def virtualLabUsername(self, value: str) -> None:
        self._set_value("virtualLabUsername", value.strip())

    @pyqtProperty(str, notify=settingsChanged)
    def virtualLabPassword(self) -> str:
        return str(self._values["virtualLabPassword"])

    @virtualLabPassword.setter
    def virtualLabPassword(self, value: str) -> None:
        self._set_value("virtualLabPassword", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showRam(self) -> bool:
        return bool(self._values["showRam"])

    @showRam.setter
    def showRam(self, value: bool) -> None:
        self._set_value("showRam", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showRamBar(self) -> bool:
        return bool(self._values["showRamBar"])

    @showRamBar.setter
    def showRamBar(self, value: bool) -> None:
        self._set_value("showRamBar", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showRamText(self) -> bool:
        return bool(self._values["showRamText"])

    @showRamText.setter
    def showRamText(self, value: bool) -> None:
        self._set_value("showRamText", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def ramWarningEnabled(self) -> bool:
        return bool(self._values["ramWarningEnabled"])

    @ramWarningEnabled.setter
    def ramWarningEnabled(self, value: bool) -> None:
        self._set_value("ramWarningEnabled", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def ramBlinkOnHigh(self) -> bool:
        return bool(self._values["ramBlinkOnHigh"])

    @ramBlinkOnHigh.setter
    def ramBlinkOnHigh(self, value: bool) -> None:
        self._set_value("ramBlinkOnHigh", value)

    @pyqtProperty(int, notify=settingsChanged)
    def ramWarningThreshold(self) -> int:
        return int(self._values["ramWarningThreshold"])

    @ramWarningThreshold.setter
    def ramWarningThreshold(self, value: int) -> None:
        self._set_value("ramWarningThreshold", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showDate(self) -> bool:
        return bool(self._values["showDate"])

    @showDate.setter
    def showDate(self, value: bool) -> None:
        self._set_value("showDate", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showTime(self) -> bool:
        return bool(self._values["showTime"])

    @showTime.setter
    def showTime(self, value: bool) -> None:
        self._set_value("showTime", value)

    @pyqtProperty(bool, notify=settingsChanged)
    def showNotifications(self) -> bool:
        return bool(self._values["showNotifications"])

    @showNotifications.setter
    def showNotifications(self, value: bool) -> None:
        self._set_value("showNotifications", value)

    @pyqtProperty(int, notify=settingsChanged)
    def dateTimeFormatMode(self) -> int:
        return int(self._values["dateTimeFormatMode"])

    @dateTimeFormatMode.setter
    def dateTimeFormatMode(self, value: int) -> None:
        self._set_value("dateTimeFormatMode", value)

    @pyqtProperty(str, notify=settingsChanged)
    def customDateFormat(self) -> str:
        return str(self._values["customDateFormat"])

    @customDateFormat.setter
    def customDateFormat(self, value: str) -> None:
        self._set_value("customDateFormat", value)

    @pyqtProperty(str, notify=settingsChanged)
    def customTimeFormat(self) -> str:
        return str(self._values["customTimeFormat"])

    @customTimeFormat.setter
    def customTimeFormat(self, value: str) -> None:
        self._set_value("customTimeFormat", value)

__all__ = ["StatusBarSettings", "ThemeSettings", "WindowSettings"]
