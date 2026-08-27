from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from features.syslog.group_service import SyslogGroupService
from features.syslog.repository import SyslogRepository


class SyslogGroupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.info_db = root / "info.db"
        self.device_db = root / "devices.db"
        sqlite3.connect(self.info_db).close()
        with closing(sqlite3.connect(self.device_db)) as conn:
            with conn:
                conn.executescript(
                    """
                    CREATE TABLE t01_devices (
                        host TEXT PRIMARY KEY, device_name TEXT, role TEXT,
                        device_type TEXT, os TEXT, connection_status TEXT
                    );
                    CREATE TABLE t02_interface_name (
                        iface_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host TEXT, interface_name TEXT, ip_address TEXT,
                        sync_status TEXT
                    );
                    CREATE TABLE t06_interface_l2 (
                        host TEXT, if_name TEXT, success TEXT
                    );
                    CREATE TABLE t06_svi_interface (
                        host TEXT, vlan_id INTEGER, ip_address TEXT,
                        sync_status TEXT
                    );
                    CREATE TABLE t06_etherchannel (
                        host TEXT, po_number INTEGER, success TEXT
                    );
                    """
                )
                for index, host in enumerate(("192.0.2.1", "192.0.2.2"), start=1):
                    conn.execute(
                        "INSERT INTO t01_devices VALUES (?, ?, 'rou', 'router', "
                        "'cisco_ios', 'connected')",
                        (host, f"R{index}"),
                    )
                    conn.execute(
                        "INSERT INTO t02_interface_name "
                        "(host, interface_name, ip_address, sync_status) "
                        "VALUES (?, 'Loopback0', ?, 'synchronized')",
                        (host, host),
                    )
                conn.execute(
                    "INSERT INTO t01_devices VALUES "
                    "('192.0.2.3', 'R3', 'rou', 'router', 'cisco_ios', 'disconnected')"
                )
                conn.execute(
                    "INSERT INTO t01_devices VALUES "
                    "('192.0.2.4', 'MT1', 'rou', 'router', 'mikrotik_routeros', 'connected')"
                )
                conn.execute(
                    "INSERT INTO t01_devices VALUES "
                    "('192.0.2.5', 'NX1', 'sw3', 'switch', 'cisco_nxos', 'connected')"
                )
        self.repository = SyslogRepository(self.info_db, self.device_db)
        self.service = SyslogGroupService(self.repository)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _common() -> dict[str, object]:
        return {
            "server_ip": "198.51.100.10",
            "protocol": "udp",
            "port": 5514,
            "trap_severity": 5,
            "timestamps": True,
            "sequence_numbers": True,
        }

    def test_options_only_include_connected_cisco_hosts_and_recommend_loopback(self) -> None:
        hosts = self.service.options()["hosts"]

        self.assertEqual([row["host"] for row in hosts], ["192.0.2.1", "192.0.2.2"])
        self.assertTrue(all(row["recommended_interface"] == "Loopback0" for row in hosts))
        self.assertEqual(hosts[0]["interfaces"][0]["name"], "Loopback0")

    def test_group_stages_shared_policy_with_independent_interfaces(self) -> None:
        result = self.service.save(
            [
                {"host": "192.0.2.1", "source_interface": "loopback0"},
                {"host": "192.0.2.2", "source_interface": "Loopback0"},
            ],
            self._common(),
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["successful"], ["192.0.2.1", "192.0.2.2"])
        for host in result["successful"]:
            row = self.repository.device_configurations(host)[0]
            self.assertEqual(row["server_ip"], "198.51.100.10")
            self.assertEqual(row["source_interface"], "Loopback0")
            self.assertEqual(row["sync_status"], "pending_apply")

    def test_group_reports_partial_failure_without_rolling_back_other_hosts(self) -> None:
        result = self.service.save(
            [
                {"host": "192.0.2.1", "source_interface": "Missing0"},
                {"host": "192.0.2.2", "source_interface": "Loopback0"},
            ],
            self._common(),
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"], result)
        self.assertEqual(result["successful"], ["192.0.2.2"])
        self.assertIn("Missing0 is not available", result["message"])
        self.assertEqual(len(self.repository.device_configurations("192.0.2.2")), 1)

    def test_group_rejects_invalid_common_policy_before_writing_any_host(self) -> None:
        common = self._common()
        common["server_ip"] = "not-an-ip"

        result = self.service.save(
            [
                {"host": "192.0.2.1", "source_interface": "Loopback0"},
                {"host": "192.0.2.2", "source_interface": "Loopback0"},
            ],
            common,
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["partial"])
        self.assertEqual(self.repository.device_configurations("192.0.2.1"), [])

    def test_group_rejects_more_than_five_hosts(self) -> None:
        result = self.service.save(
            [
                {"host": f"192.0.2.{index}", "source_interface": "Loopback0"}
                for index in range(1, 7)
            ],
            self._common(),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Syslog Group supports at most 5 hosts")


if __name__ == "__main__":
    unittest.main()
