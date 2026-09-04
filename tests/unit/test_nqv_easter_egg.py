from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch

from core.app_paths import AppPaths
from main import APP_DESKTOP_FILE_NAME, _application_icon_path, _configure_qt_logging, _runtime_arguments


class NqvEasterEggTests(unittest.TestCase):
    def test_application_icon_uses_native_format(self):
        self.assertEqual(APP_DESKTOP_FILE_NAME, "cams")
        self.assertEqual(_application_icon_path("linux").name, "logo.png")
        self.assertEqual(_application_icon_path("win32").name, "logo.ico")
        self.assertTrue(_application_icon_path("linux").is_file())
        self.assertTrue(_application_icon_path("win32").is_file())

    def test_wayland_filter_suppresses_known_qt_diagnostics(self):
        environment = {
            "XDG_SESSION_TYPE": "wayland",
            "QT_LOGGING_RULES": "qt.qml.binding.removal.info=true",
        }
        with patch("main.sys.platform", "linux"), patch.dict(
            os.environ, environment, clear=True
        ):
            _configure_qt_logging()
            self.assertEqual(
                os.environ["QT_LOGGING_RULES"],
                "qt.qml.binding.removal.info=true;qt.qpa.wayland.textinput=false;"
                "qt.qpa.services=false",
            )

    def test_v_flag_is_private_and_removed_before_qt(self):
        arguments, mode = _runtime_arguments(["main.py", "-v", "--style", "Fusion"])
        self.assertEqual(mode, "nqv")
        self.assertEqual(arguments, ["main.py", "--style", "Fusion"])

    def test_default_launch_does_not_enable_easter_egg(self):
        arguments, mode = _runtime_arguments(["main.py"])
        self.assertEqual(mode, "")
        self.assertEqual(arguments, ["main.py"])

    def test_hidden_asset_is_served_as_svg_data_url(self):
        url = AppPaths().hiddenBrandLogo().toString()
        self.assertTrue(url.startswith("data:image/svg+xml;base64,"))
        payload = base64.b64decode(url.split(",", 1)[1]).decode("utf-8")
        self.assertIn("<svg", payload)
        self.assertIn('viewBox="0 0 3892 3892"', payload)

    def test_p_flag_selects_ptit_and_last_brand_flag_wins(self):
        arguments, mode = _runtime_arguments(["main.py", "-v", "-p"])
        self.assertEqual(arguments, ["main.py"])
        self.assertEqual(mode, "ptit")

    def test_hidden_ptit_asset_is_served_as_svg_data_url(self):
        url = AppPaths().hiddenPtitLogo().toString()
        self.assertTrue(url.startswith("data:image/svg+xml;base64,"))
        payload = base64.b64decode(url.split(",", 1)[1]).decode("utf-8")
        self.assertIn("<svg", payload)
        self.assertIn('viewBox="0 0 1000 1000"', payload)
