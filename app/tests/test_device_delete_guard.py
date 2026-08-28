from __future__ import annotations

import unittest
from pathlib import Path

from core.database.device_slots import DeviceSlotsMixin


class DeviceDeleteGuardTests(unittest.TestCase):
    def test_backend_rejects_host_deletion(self) -> None:
        result = DeviceSlotsMixin().deleteDevice("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertEqual(result["message"], "Host deletion is disabled.")

    def test_device_panel_disables_menu_and_delete_shortcut(self) -> None:
        root = Path(__file__).resolve().parents[1] / "UI" / "qml"
        panel = (root / "panels" / "DevicesPanel.qml").read_text(encoding="utf-8")
        menu = (
            root / "sidebar" / "devices" / "DeviceContextMenu.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("readonly property bool hostDeletionEnabled: false", panel)
        self.assertIn("allowHostDeletion: devicesPanel.hostDeletionEnabled", panel)
        self.assertIn(
            "devicesPanel.deviceShortcutEnabled && devicesPanel.hostDeletionEnabled",
            panel,
        )
        self.assertIn("enabled: contextMenu.allowHostDeletion", menu)


if __name__ == "__main__":
    unittest.main()
