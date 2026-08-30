from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database.device_slots import DeviceSlotsMixin
from features.config_backup.service import ConfigBackupService


class DeviceDeleteGuardTests(unittest.TestCase):
    def test_backend_cascades_host_data_across_workspace_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            device_db = root / "device.db"
            info_db = root / "info.db"
            with sqlite3.connect(device_db) as conn:
                conn.executescript(
                    """
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE t01_devices (host TEXT PRIMARY KEY);
                    CREATE TABLE child_config (
                        id INTEGER PRIMARY KEY,
                        host TEXT NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE
                    );
                    INSERT INTO t01_devices(host) VALUES ('192.0.2.10'), ('192.0.2.20');
                    INSERT INTO child_config(host) VALUES ('192.0.2.10'), ('192.0.2.20');
                    """
                )
            with sqlite3.connect(info_db) as conn:
                conn.executescript(
                    """
                    CREATE TABLE collected (id INTEGER PRIMARY KEY, host TEXT NOT NULL);
                    CREATE TABLE syslog (id INTEGER PRIMARY KEY, device_host TEXT NOT NULL);
                    CREATE TABLE collection_parent (id INTEGER PRIMARY KEY, host TEXT NOT NULL);
                    CREATE TABLE collection_child (
                        id INTEGER PRIMARY KEY,
                        parent_id INTEGER NOT NULL
                            REFERENCES collection_parent(id) ON DELETE CASCADE
                    );
                    INSERT INTO collected(host) VALUES ('192.0.2.10'), ('192.0.2.20');
                    INSERT INTO syslog(device_host) VALUES ('192.0.2.10'), ('192.0.2.20');
                    INSERT INTO collection_parent(id, host) VALUES
                        (1, '192.0.2.10'), (2, '192.0.2.20');
                    INSERT INTO collection_child(parent_id) VALUES (1), (2);
                    """
                )
            backup_service = ConfigBackupService(root / "backup")
            host_backup = root / "backup" / "192.0.2.10" / "cfg"
            host_backup.mkdir(parents=True)
            (host_backup / "running-config.txt").write_text("test", encoding="utf-8")
            backend = DeviceSlotsMixin()
            backend.db_path = device_db
            backend.info_db_path = info_db
            backend._config_backup_service = backup_service

            result = backend.deleteDevice("192.0.2.10")

            self.assertTrue(result["ok"])
            self.assertEqual(result["deletedInfoRows"], 3)
            self.assertTrue(result["deletedBackups"])
            self.assertFalse((root / "backup" / "192.0.2.10").exists())
            with sqlite3.connect(device_db) as conn:
                self.assertEqual(
                    conn.execute("SELECT host FROM t01_devices ORDER BY host").fetchall(),
                    [("192.0.2.20",)],
                )
                self.assertEqual(
                    conn.execute("SELECT host FROM child_config ORDER BY host").fetchall(),
                    [("192.0.2.20",)],
                )
            with sqlite3.connect(info_db) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM collected").fetchone(), (1,))
                self.assertEqual(conn.execute("SELECT count(*) FROM syslog").fetchone(), (1,))
                self.assertEqual(conn.execute("SELECT count(*) FROM collection_child").fetchone(), (1,))

    def test_device_delete_is_right_click_only_and_requires_commitment(self) -> None:
        root = Path(__file__).resolve().parents[1] / "UI" / "qml"
        panel = (root / "panels" / "DevicesPanel.qml").read_text(encoding="utf-8")
        menu = (
            root / "sidebar" / "devices" / "DeviceContextMenu.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("readonly property bool hostDeletionEnabled: true", panel)
        self.assertIn("allowHostDeletion: devicesPanel.hostDeletionEnabled", panel)
        self.assertNotIn('Shortcut { sequence: "Del"', panel)
        self.assertNotIn("function handleShortcutDelete()", panel)
        self.assertIn('objectName: "deviceDeleteAcknowledgement"', panel)
        self.assertIn('objectName: "deviceDeleteConfirmationField"', panel)
        self.assertIn('readonly property string confirmationPhrase: "DELETE " + targetIp', panel)
        self.assertIn("enabled: contextMenu.allowHostDeletion", menu)
        self.assertIn('shortcutText: "Right-click only"', menu)

    def test_quit_waits_for_the_workspace_close_transaction(self) -> None:
        qml_root = Path(__file__).resolve().parents[1] / "UI" / "qml"
        main = (qml_root / "app" / "Main.qml").read_text(encoding="utf-8")
        registry = (qml_root / "shared" / "CommandRegistry.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("function requestQuit()", main)
        self.assertIn("root.workspaceBackend.requestCloseWorkspace()", main)
        self.assertIn("function onWorkspaceCloseCompleted()", main)
        self.assertIn("quitHandler: function() { return root.requestQuit() }", main)
        self.assertIn("onClosing: close =>", main)
        self.assertIn("close.accepted = false", main)
        self.assertIn("property bool workspaceBusy: false", registry)


if __name__ == "__main__":
    unittest.main()
