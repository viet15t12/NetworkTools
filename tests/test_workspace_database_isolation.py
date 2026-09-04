from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.database.manager import DatabaseManager
from infrastructure.workspace import WorkspaceService


class WorkspaceDatabaseIsolationTests(unittest.TestCase):
    def test_batch_device_insert_returns_added_rows_and_skips_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = WorkspaceService()
            project = service.create_project("batch", root / "batch.ntp")
            manager = DatabaseManager(
                db_path=project.device_network_db,
                info_db_path=project.info_collected_db,
            )
            try:
                payload = [
                    {
                        "host": "10.20.0.1", "name": "Core-R1",
                        "protocol": "SSH", "port": "22", "username": "admin",
                        "password": "secret", "os": "cisco_ios", "role": "rou",
                    },
                    {
                        "host": "10.20.0.2", "name": "Access-SW1",
                        "protocol": "TELNET", "port": "23", "os": "cisco_ios",
                        "role": "sw2",
                    },
                ]
                result = manager.addDevicesBatch(payload)
                self.assertTrue(result["ok"])
                self.assertEqual(result["added"], 2)
                self.assertEqual(result["skipped"], 0)
                self.assertEqual([row["ip"] for row in result["devices"]], ["10.20.0.1", "10.20.0.2"])

                repeated = manager.addDevicesBatch(payload)
                self.assertFalse(repeated["ok"])
                self.assertEqual(repeated["added"], 0)
                self.assertEqual(repeated["skipped"], 2)
                self.assertEqual(len(manager.getDevices()), 2)
            finally:
                manager.shutdown()
                service.close_project(project)

    def test_switching_projects_does_not_reuse_device_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = WorkspaceService()
            first = service.create_project("test1", root / "test1.ntp")
            second = None
            manager = DatabaseManager(
                db_path=first.device_network_db,
                info_db_path=first.info_collected_db,
            )
            try:
                self.assertTrue(
                    manager.addDevice(
                        "10.2.3.1", "router", "ssh", "22", "user", "pass"
                    )
                )
                self.assertEqual(
                    [row["ip"] for row in manager.getDevices()], ["10.2.3.1"]
                )

                second = service.create_project("test2", root / "test2.ntp")
                self.assertTrue(
                    manager.set_workspace_databases(
                        second.device_network_db, second.info_collected_db
                    )
                )
                self.assertEqual(manager.getDevices(), [])
            finally:
                manager.shutdown()
                service.close_project(first)
                service.close_project(second)


if __name__ == "__main__":
    unittest.main()
