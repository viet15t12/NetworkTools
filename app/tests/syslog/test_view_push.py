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
    def send_command(self, command: str) -> str:
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
    def __init__(self, info_db: Path, device_db: Path) -> None:
        self.info_db_path = info_db
        self.db_path = device_db

    def _routing_device_context(self, host: str):
        return {
            "platform": "cisco_ios",
            "template_folder": "cisco_ios",
            "method": "SSH",
        }

    def _is_view_push_dev_host(self, host: str) -> bool:
        return False

    def reconcileViewPushSnapshot(self, host: str, connector):
        return {"ok": True, "message": "Snapshot updated.", "snapshotUpdated": True}


class SyslogViewPushTests(unittest.TestCase):
    def test_push_reuses_the_already_locked_host_connector(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            info_db = root / "info.db"
            device_db = root / "device.db"
            sqlite3.connect(info_db).close()
            with sqlite3.connect(device_db) as conn:
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

            repository = SyslogRepository(info_db, device_db)
            repository.save_configuration(
                HOST,
                {
                    "server_ip": SERVER,
                    "protocol": "udp",
                    "port": 514,
                    "source_interface": "Loopback0",
                    "trap_severity": 5,
                },
            )
            registry = _NonReentrantRegistry()
            controller = SyslogViewPushController(
                _Database(info_db, device_db), registry
            )

            preview = controller.preview(HOST, "servers")
            result = controller.push(HOST, "servers")

            self.assertTrue(preview["ok"], preview)
            self.assertIn(f"logging host {SERVER} transport udp port 514", preview["commands"])
            self.assertIn("logging trap notifications", preview["commands"])
            self.assertTrue(result["ok"], result)
            self.assertEqual(registry.calls, 1)
            self.assertEqual(
                repository.device_configurations(HOST)[0]["sync_status"],
                "synchronized",
            )


if __name__ == "__main__":
    unittest.main()
