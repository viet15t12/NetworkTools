from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from features.syslog.repository import SyslogRepository
from features.syslog.view_push import SyslogViewPushController


HOST = "192.0.2.1"
SERVER = "192.0.2.100"


class _Connection:
    def __init__(self) -> None:
        self.show_commands: list[str] = []
        self.config_batches: list[list[str]] = []

    def send_command(self, command: str) -> str:
        self.show_commands.append(command)
        if command == "show ip interface brief":
            return (
                "Interface IP-Address OK? Method Status Protocol\n"
                f"Loopback0 {HOST} YES manual up up"
            )
        return (
            f"logging host {SERVER} transport udp port 514\n"
            "logging source-interface Loopback0"
        )

    def send_config_set(self, commands, **kwargs) -> str:
        self.config_batches.append(list(commands))
        return "OK"

    def save_config(self, **kwargs) -> str:
        return "Copy complete."


class _Connector:
    def __init__(self) -> None:
        self.connection = _Connection()


class _NonReentrantRegistry:
    def __init__(self) -> None:
        self.active = False
        self.calls = 0
        self.connector = _Connector()

    def execute(self, host, operation, *, ensure_open=True):
        if self.active:
            raise RuntimeError("nested session execution")
        self.active = True
        self.calls += 1
        try:
            return {"ok": True, "value": operation(self.connector)}
        finally:
            self.active = False


class _Database:
    def __init__(
        self, info_db: Path, device_db: Path, template_folder: str = "cisco_ios"
    ) -> None:
        self.info_db_path = info_db
        self.db_path = device_db
        self.template_folder = template_folder

    def _routing_device_context(self, host: str):
        return {
            "platform": self.template_folder,
            "template_folder": self.template_folder,
            "method": "SSH",
        }

    def _is_view_push_dev_host(self, host: str) -> bool:
        return False

    def reconcileViewPushSnapshot(self, host: str, connector):
        return {"ok": True, "message": "Snapshot updated.", "snapshotUpdated": True}


class SyslogViewPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.info_db = root / "info.db"
        self.device_db = root / "device.db"
        sqlite3.connect(self.info_db).close()
        with sqlite3.connect(self.device_db) as conn:
            conn.execute(
                "CREATE TABLE t01_devices (host TEXT, device_name TEXT, "
                "device_type TEXT, os TEXT, connection_status TEXT)"
            )
            conn.execute(
                "INSERT INTO t01_devices VALUES (?, 'R1', 'router', "
                "'cisco_ios', 'connected')",
                (HOST,),
            )
            conn.execute(
                "CREATE TABLE t02_interface_name (host TEXT, ip_address TEXT, "
                "shutdown INTEGER, sync_status TEXT, iface_id INTEGER, "
                "interface_name TEXT)"
            )
        self.repository = SyslogRepository(self.info_db, self.device_db)
        self.repository.save_configuration(
            HOST,
            {
                "server_ip": SERVER,
                "protocol": "udp",
                "port": 514,
                "source_interface": "Loopback0",
                "trap_severity": 5,
            },
        )
        self.registry = _NonReentrantRegistry()
        self.controller = SyslogViewPushController(
            _Database(self.info_db, self.device_db), self.registry
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_push_reuses_the_already_locked_host_connector(self) -> None:
        preview = self.controller.preview(HOST, "servers")
        result = self.controller.push(HOST, "servers")

        self.assertTrue(preview["ok"], preview)
        self.assertIn(f"logging host {SERVER} transport udp port 514", preview["commands"])
        self.assertIn("logging trap notifications", preview["commands"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.registry.calls, 1)
        self.assertEqual(
            self.repository.device_configurations(HOST)[0]["sync_status"],
            "synchronized",
        )

    def test_apply_only_defers_all_show_commands_and_database_sync(self) -> None:
        result = self.controller.push_apply_only(HOST, "servers")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["postPushPending"])
        self.assertIn("postPushContext", result)
        self.assertEqual(self.registry.connector.connection.show_commands, [])
        self.assertEqual(len(self.registry.connector.connection.config_batches), 1)
        self.assertEqual(
            self.repository.device_configurations(HOST)[0]["sync_status"],
            "pending_apply",
        )

    def test_preview_accepts_ios_xe_platform_used_by_new_device_workflow(self) -> None:
        controller = SyslogViewPushController(
            _Database(self.info_db, self.device_db, "cisco_xe"), self.registry
        )

        result = controller.preview(HOST, "servers")

        self.assertTrue(result["ok"], result)
        self.assertIn("logging host", result["commands"])


if __name__ == "__main__":
    unittest.main()
