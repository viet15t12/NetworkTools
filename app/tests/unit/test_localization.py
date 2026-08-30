from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QSettings

from core.localization import LanguageSettings


class LanguageSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temporary.name) / "language.ini"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def settings(self) -> QSettings:
        return QSettings(str(self.settings_path), QSettings.Format.IniFormat)

    def test_language_choice_is_persisted_and_invalid_values_fall_back_to_english(self):
        first = LanguageSettings(settings=self.settings())
        self.assertEqual(first.language, "en")

        first.setLanguage("vi")

        restored = LanguageSettings(settings=self.settings())
        self.assertEqual(restored.language, "vi")
        self.assertTrue(restored.isVietnamese)

        restored.setLanguage("unsupported")
        self.assertEqual(restored.language, "en")

    def test_english_mode_returns_notification_without_changes(self):
        backend = LanguageSettings(settings=self.settings())

        self.assertEqual(
            backend.translate("Connecting to router-01..."),
            "Connecting to router-01...",
        )

    def test_vietnamese_notification_keeps_dynamic_host_and_technical_terms(self):
        backend = LanguageSettings(settings=self.settings())
        backend.setLanguage("vi")

        self.assertEqual(
            backend.translate("Connecting to router-01..."),
            "Đang kết nối tới router-01...",
        )
        translated = backend.translate(
            "Technical terms such as host, SSH, Telnet, VLAN, OSPF, workspace, database, and CLI remain unchanged."
        )
        for technical_term in (
            "host",
            "SSH",
            "Telnet",
            "VLAN",
            "OSPF",
            "workspace",
            "database",
            "CLI",
        ):
            self.assertIn(technical_term, translated)

    def test_unknown_device_or_cli_output_is_never_machine_translated(self):
        backend = LanguageSettings(settings=self.settings())
        backend.setLanguage("vi")
        raw_output = "% Invalid input detected at '^' marker."

        self.assertEqual(backend.translate(raw_output), raw_output)


if __name__ == "__main__":
    unittest.main()
