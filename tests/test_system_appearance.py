from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.settings import SystemAppearance


class SystemAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_linux_prefers_gsettings_over_qt_fallback(self) -> None:
        with (
            patch("core.settings.sys.platform", "linux"),
            patch.dict(
                "core.settings.os.environ",
                {"XDG_CURRENT_DESKTOP": "GNOME"},
                clear=False,
            ),
            patch.object(SystemAppearance, "_portal_color_scheme", return_value=None),
            patch.object(SystemAppearance, "_gsettings_color_scheme", return_value=2),
            patch.object(SystemAppearance, "_kde_color_scheme", return_value=None),
            patch.object(SystemAppearance, "_gtk_color_scheme", return_value=None),
            patch.object(SystemAppearance, "_qt_color_scheme", return_value=1),
        ):
            appearance = SystemAppearance(poll_interval_ms=60_000)

        self.assertTrue(appearance.prefersDark)
        self.assertEqual(appearance.colorScheme, SystemAppearance.DARK)

    def test_kde_preference_wins_over_installed_gsettings(self) -> None:
        with (
            patch("core.settings.sys.platform", "linux"),
            patch.dict(
                "core.settings.os.environ",
                {"XDG_CURRENT_DESKTOP": "KDE"},
                clear=False,
            ),
            patch.object(SystemAppearance, "_portal_color_scheme", return_value=None),
            patch.object(SystemAppearance, "_gsettings_color_scheme", return_value=1),
            patch.object(SystemAppearance, "_kde_color_scheme", return_value=2),
            patch.object(SystemAppearance, "_gtk_color_scheme", return_value=None),
            patch.object(SystemAppearance, "_qt_color_scheme", return_value=1),
        ):
            appearance = SystemAppearance(poll_interval_ms=60_000)

        self.assertTrue(appearance.prefersDark)

    def test_gsettings_prefer_dark_value_is_parsed(self) -> None:
        with (
            patch("core.settings.shutil.which", return_value="/usr/bin/gsettings"),
            patch(
                "core.settings.subprocess.run",
                return_value=CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="'prefer-dark'\n",
                    stderr="",
                ),
            ),
        ):
            appearance = SystemAppearance(poll_interval_ms=60_000)

        self.assertEqual(
            appearance._gsettings_color_scheme(),
            SystemAppearance.DARK,
        )

    def test_gtk_dark_preference_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            config_home = Path(root)
            settings = config_home / "gtk-4.0" / "settings.ini"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                "\n".join((
                    "[Settings]",
                    "gtk-application-prefer-dark-theme=true",
                    "gtk-theme-name=Adwaita",
                )),
                encoding="utf-8",
            )
            with patch.dict(
                "core.settings.os.environ",
                {"XDG_CONFIG_HOME": str(config_home), "GTK_THEME": ""},
                clear=False,
            ):
                appearance = SystemAppearance(poll_interval_ms=60_000)
                self.assertEqual(
                    appearance._gtk_color_scheme(),
                    SystemAppearance.DARK,
                )

    def test_kde_background_luminance_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            config_home = Path(root)
            kdeglobals = config_home / "kdeglobals"
            kdeglobals.write_text(
                "\n".join((
                    "[KDE]",
                    "ColorScheme=Breeze",
                    "[Colors:Window]",
                    "BackgroundNormal=35,38,41",
                )),
                encoding="utf-8",
            )
            with patch.dict(
                "core.settings.os.environ",
                {"XDG_CONFIG_HOME": str(config_home)},
                clear=False,
            ):
                appearance = SystemAppearance(poll_interval_ms=60_000)
                self.assertEqual(
                    appearance._kde_color_scheme(),
                    SystemAppearance.DARK,
                )

    def test_refresh_emits_only_when_preference_changes(self) -> None:
        with patch.object(
            SystemAppearance,
            "_detect_color_scheme",
            return_value=1,
        ):
            appearance = SystemAppearance(poll_interval_ms=60_000)
        changes: list[bool] = []
        appearance.appearanceChanged.connect(
            lambda: changes.append(appearance.prefersDark)
        )

        with patch.object(
            appearance,
            "_detect_color_scheme",
            side_effect=(1, 2, 2),
        ):
            appearance.refresh()
            appearance.refresh()
            appearance.refresh()

        self.assertEqual(changes, [True])


if __name__ == "__main__":
    unittest.main()
