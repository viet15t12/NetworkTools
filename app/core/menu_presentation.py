"""Persistent menu-style preference and platform resolution for QML."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QSettings, pyqtProperty, pyqtSignal, pyqtSlot

from infrastructure.system.desktop_environment import (
    DesktopEnvironmentDetector,
    DesktopEnvironmentInfo,
    detection_failure_info,
)


LOGGER = logging.getLogger(__name__)


class MenuPresentationController(QObject):
    """Resolve Auto/Custom/Global into a safe rendering flag."""

    stateChanged = pyqtSignal()

    AUTO = "auto"
    CUSTOM = "custom"
    GLOBAL = "global"
    SETTINGS_KEY = "Appearance/menuStyle"
    VALID_STYLES = frozenset({AUTO, CUSTOM, GLOBAL})

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        detector: DesktopEnvironmentDetector | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector = (
            detector if detector is not None else DesktopEnvironmentDetector()
        )
        self._settings = settings if settings is not None else QSettings()
        self._native_runtime_failure = ""
        self._environment = self._detect_environment()
        stored_style = self._settings.value(self.SETTINGS_KEY, self.AUTO)
        self._configured_style = self._normalize_style(stored_style)
        if str(stored_style or "").strip().casefold() != self._configured_style:
            self._persist_style()
        self._active_style = self._resolve_style(self._configured_style)

    @classmethod
    def _normalize_style(cls, value: object) -> str:
        normalized = str(value or "").strip().casefold()
        if normalized == "native":
            return cls.GLOBAL
        return normalized if normalized in cls.VALID_STYLES else cls.AUTO

    def _persist_style(self) -> None:
        self._settings.setValue(self.SETTINGS_KEY, self._configured_style)
        self._settings.sync()

    def _detect_environment(self) -> DesktopEnvironmentInfo:
        try:
            return self._detector.detect()
        except Exception:
            LOGGER.warning(
                "Menu environment detection failed; using the custom menu.",
                exc_info=True,
            )
            return detection_failure_info()

    def _native_global_available(self) -> bool:
        return not self._native_runtime_failure and (
            self._environment.platform_family == "macos" or (
                self._environment.platform_family == "linux"
                and self._environment.global_menu_registrar_available
            )
        )

    def _recommended_style(self) -> str:
        if (
            self._environment.platform_family == "macos"
            and self._native_global_available()
        ):
            return self.GLOBAL
        if (
            self._environment.platform_family == "linux"
            and self._environment.desktop_family in {"kde", "unity"}
            and self._native_global_available()
        ):
            return self.GLOBAL
        return self.CUSTOM

    def _resolve_style(self, configured_style: str) -> str:
        if configured_style == self.AUTO:
            return self._recommended_style()
        if configured_style == self.GLOBAL:
            return self.GLOBAL if self._native_global_available() else self.CUSTOM
        return self.CUSTOM

    @pyqtProperty(str, notify=stateChanged)
    def configuredStyle(self) -> str:
        return self._configured_style

    @configuredStyle.setter
    def configuredStyle(self, value: str) -> None:
        normalized = self._normalize_style(value)
        if normalized == self._configured_style:
            return
        self._configured_style = normalized
        self._persist_style()
        self.stateChanged.emit()

    @pyqtProperty(str, notify=stateChanged)
    def recommendedStyle(self) -> str:
        return self._recommended_style()

    @pyqtProperty(str, notify=stateChanged)
    def resolvedStyle(self) -> str:
        return self._resolve_style(self._configured_style)

    @pyqtProperty(str, notify=stateChanged)
    def activeStyle(self) -> str:
        return self._active_style

    @pyqtProperty(bool, notify=stateChanged)
    def isCustomActive(self) -> bool:
        return self._active_style == self.CUSTOM

    @pyqtProperty(bool, notify=stateChanged)
    def isGlobalActive(self) -> bool:
        return self._active_style == self.GLOBAL

    @pyqtProperty(bool, notify=stateChanged)
    def nativeGlobalAvailable(self) -> bool:
        return self._native_global_available()

    @pyqtProperty(str, notify=stateChanged)
    def platformFamily(self) -> str:
        return self._environment.platform_family

    @pyqtProperty(str, notify=stateChanged)
    def desktopFamily(self) -> str:
        return self._environment.desktop_family

    @pyqtProperty(str, notify=stateChanged)
    def sessionType(self) -> str:
        return self._environment.session_type

    @pyqtProperty(str, notify=stateChanged)
    def qtPlatformPlugin(self) -> str:
        return self._environment.qt_platform_plugin

    @pyqtProperty(str, notify=stateChanged)
    def capabilityReason(self) -> str:
        if self._native_runtime_failure:
            return "native-presenter-load-failed"
        return self._environment.capability_reason

    @pyqtProperty(str, notify=stateChanged)
    def fallbackMessage(self) -> str:
        if self._native_runtime_failure and self._configured_style != self.CUSTOM:
            return self._native_runtime_failure
        if self._configured_style != self.GLOBAL or self._native_global_available():
            return ""
        if self._environment.platform_family == "linux":
            return (
                "A compatible desktop Global Menu service is not available; "
                "CAMS will use the in-window menu."
            )
        return (
            "Native Global menus are not available on this platform; "
            "CAMS will use the in-window menu."
        )

    @pyqtProperty(bool, notify=stateChanged)
    def restartRequired(self) -> bool:
        return self.resolvedStyle != self._active_style

    @pyqtSlot()
    def resetToAuto(self) -> None:
        self.configuredStyle = self.AUTO

    @pyqtSlot(str)
    def reportNativeFailure(self, message: str) -> None:
        if self._active_style != self.GLOBAL:
            return
        normalized = str(message or "").strip()
        if not normalized:
            normalized = (
                "The Native Global menu presenter could not be loaded; "
                "CAMS is using the in-window menu."
            )
        if (
            normalized == self._native_runtime_failure
            and self._active_style == self.CUSTOM
        ):
            return
        self._native_runtime_failure = normalized
        self._active_style = self.CUSTOM
        self.stateChanged.emit()

    @pyqtSlot()
    def refreshDetection(self) -> None:
        environment = self._detect_environment()
        if environment == self._environment:
            return
        self._environment = environment
        self.stateChanged.emit()


__all__ = ["DesktopEnvironmentInfo", "MenuPresentationController"]
