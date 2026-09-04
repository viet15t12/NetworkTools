from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QSettings

from core.menu_presentation import MenuPresentationController
from infrastructure.system.desktop_environment import (
    GLOBAL_MENU_PROBE_TIMEOUT_MS,
    DesktopEnvironmentDetector,
    DesktopEnvironmentInfo,
)


class StaticDetector:
    def __init__(self, environment: DesktopEnvironmentInfo) -> None:
        self.environment = environment

    def detect(self) -> DesktopEnvironmentInfo:
        return self.environment


class RaisingDetector:
    def detect(self) -> DesktopEnvironmentInfo:
        raise RuntimeError("desktop probe failed")


def environment(
    platform: str,
    desktop: str = "none",
    *,
    registrar: bool = False,
    reason: str = "unsupported-platform",
) -> DesktopEnvironmentInfo:
    return DesktopEnvironmentInfo(
        platform_family=platform,
        desktop_family=desktop,
        session_type="unknown",
        qt_platform_plugin="test",
        global_menu_registrar_available=registrar,
        capability_reason=reason,
    )


class DesktopEnvironmentDetectorTests(unittest.TestCase):
    def test_global_menu_probe_has_a_short_startup_bound(self) -> None:
        self.assertGreater(GLOBAL_MENU_PROBE_TIMEOUT_MS, 0)
        self.assertLessEqual(GLOBAL_MENU_PROBE_TIMEOUT_MS, 500)

    def test_detects_kde_wayland_and_global_menu_registrar(self) -> None:
        detector = DesktopEnvironmentDetector(
            platform_id="linux",
            environ={
                "XDG_CURRENT_DESKTOP": "KDE:Plasma",
                "XDG_SESSION_TYPE": "wayland",
            },
            qt_platform_plugin="wayland",
            registrar_probe=lambda: True,
        )

        result = detector.detect()

        self.assertEqual(result.platform_family, "linux")
        self.assertEqual(result.desktop_family, "kde")
        self.assertEqual(result.session_type, "wayland")
        self.assertEqual(result.qt_platform_plugin, "wayland")
        self.assertTrue(result.global_menu_registrar_available)
        self.assertEqual(result.capability_reason, "dbus-registrar-present")

    def test_detects_gnome_without_assuming_global_menu_support(self) -> None:
        detector = DesktopEnvironmentDetector(
            platform_id="linux",
            environ={
                "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
                "XDG_SESSION_TYPE": "x11",
            },
            qt_platform_plugin="xcb",
            registrar_probe=lambda: False,
        )

        result = detector.detect()

        self.assertEqual(result.desktop_family, "gnome")
        self.assertEqual(result.session_type, "x11")
        self.assertFalse(result.global_menu_registrar_available)
        self.assertEqual(result.capability_reason, "dbus-registrar-missing")

    def test_non_linux_platforms_do_not_probe_the_linux_registrar(self) -> None:
        probe_count = 0

        def probe() -> bool:
            nonlocal probe_count
            probe_count += 1
            return True

        macos = DesktopEnvironmentDetector(
            platform_id="darwin",
            environ={},
            qt_platform_plugin="cocoa",
            registrar_probe=probe,
        ).detect()
        windows = DesktopEnvironmentDetector(
            platform_id="win32",
            environ={},
            qt_platform_plugin="windows",
            registrar_probe=probe,
        ).detect()

        self.assertEqual(macos.platform_family, "macos")
        self.assertEqual(macos.capability_reason, "macos-system-menu")
        self.assertEqual(windows.platform_family, "windows")
        self.assertEqual(windows.capability_reason, "unsupported-platform")
        self.assertEqual(probe_count, 0)


class MenuPresentationControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def settings(self, name: str) -> QSettings:
        path = Path(self.temporary.name) / f"{name}.ini"
        value = QSettings(str(path), QSettings.Format.IniFormat)
        value.clear()
        return value

    def test_auto_policy_prefers_macos_and_capable_kde(self) -> None:
        macos = MenuPresentationController(
            detector=StaticDetector(environment("macos")),
            settings=self.settings("auto-macos"),
        )
        kde = MenuPresentationController(
            detector=StaticDetector(
                environment(
                    "linux",
                    "kde",
                    registrar=True,
                    reason="dbus-registrar-present",
                )
            ),
            settings=self.settings("auto-kde"),
        )

        self.assertEqual(macos.activeStyle, "global")
        self.assertTrue(macos.isGlobalActive)
        self.assertEqual(kde.recommendedStyle, "global")
        self.assertEqual(kde.activeStyle, "global")

    def test_auto_uses_custom_without_supported_global_menu(self) -> None:
        cases = (
            environment("windows"),
            environment("linux", "gnome", reason="dbus-registrar-missing"),
            environment("linux", "kde", reason="dbus-registrar-missing"),
        )
        for index, facts in enumerate(cases):
            with self.subTest(facts=facts):
                controller = MenuPresentationController(
                    detector=StaticDetector(facts),
                    settings=self.settings(f"auto-custom-{index}"),
                )
                self.assertEqual(controller.activeStyle, "custom")
                self.assertTrue(controller.isCustomActive)

    def test_detection_failure_falls_back_to_custom_without_aborting(self) -> None:
        with self.assertLogs("core.menu_presentation", level="WARNING"):
            controller = MenuPresentationController(
                detector=RaisingDetector(),
                settings=self.settings("detection-failure"),
            )

        self.assertEqual(controller.activeStyle, "custom")
        self.assertEqual(controller.resolvedStyle, "custom")
        self.assertEqual(controller.capabilityReason, "detection-failed")
        self.assertFalse(controller.nativeGlobalAvailable)

    def test_native_presenter_failure_synchronizes_runtime_fallback_state(self) -> None:
        controller = MenuPresentationController(
            detector=StaticDetector(environment("macos")),
            settings=self.settings("native-runtime-failure"),
        )

        controller.reportNativeFailure("Native presenter import failed.")

        self.assertEqual(controller.activeStyle, "custom")
        self.assertEqual(controller.resolvedStyle, "custom")
        self.assertFalse(controller.nativeGlobalAvailable)
        self.assertEqual(controller.capabilityReason, "native-presenter-load-failed")
        self.assertEqual(controller.fallbackMessage, "Native presenter import failed.")
        self.assertFalse(controller.restartRequired)

    def test_global_override_falls_back_safely_and_requires_restart(self) -> None:
        settings = self.settings("fallback")
        controller = MenuPresentationController(
            detector=StaticDetector(environment("windows")),
            settings=settings,
        )

        controller.configuredStyle = "global"

        self.assertEqual(controller.configuredStyle, "global")
        self.assertEqual(controller.resolvedStyle, "custom")
        self.assertEqual(controller.activeStyle, "custom")
        self.assertFalse(controller.restartRequired)
        self.assertIn("not available", controller.fallbackMessage)
        self.assertEqual(settings.value("Appearance/menuStyle"), "global")

    def test_override_is_persisted_and_legacy_native_value_is_migrated(self) -> None:
        settings = self.settings("persisted")
        settings.setValue("Appearance/menuStyle", "native")
        settings.sync()
        detector = StaticDetector(environment("macos"))

        migrated = MenuPresentationController(detector=detector, settings=settings)
        migrated.configuredStyle = "custom"
        restored = MenuPresentationController(detector=detector, settings=settings)

        self.assertEqual(migrated.activeStyle, "global")
        self.assertTrue(migrated.restartRequired)
        self.assertEqual(restored.configuredStyle, "custom")
        self.assertEqual(restored.activeStyle, "custom")

    def test_refresh_updates_resolution_without_switching_active_style(self) -> None:
        detector = StaticDetector(
            environment("linux", "kde", reason="dbus-registrar-missing")
        )
        controller = MenuPresentationController(
            detector=detector,
            settings=self.settings("refresh"),
        )
        detector.environment = environment(
            "linux",
            "kde",
            registrar=True,
            reason="dbus-registrar-present",
        )

        controller.refreshDetection()

        self.assertEqual(controller.resolvedStyle, "global")
        self.assertEqual(controller.activeStyle, "custom")
        self.assertTrue(controller.restartRequired)


if __name__ == "__main__":
    unittest.main()
