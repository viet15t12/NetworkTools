from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from features.devices.sync_state import parse_running_config_sections, sync_device_state
from scripts.build_databases import combine_sql


SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "infrastructure"
    / "database"
    / "schemas"
    / "device_network"
)


CONFIG = """
interface GigabitEthernet0/0
 ip address 192.0.2.1 255.255.255.0
 ip helper-address 10.10.10.10
 ip helper-address 10.10.10.11
 ip helper-address 10.10.10.10
!
interface GigabitEthernet0/1
 ip address 198.51.100.1 255.255.255.0
 ip helper-address 10.20.20.20
 ip helper-address vrf BLUE 10.30.30.30
!
"""


class DhcpHelperSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(combine_sql(SCHEMA_DIR))
            conn.execute("INSERT INTO t01_devices(host, role) VALUES ('r1', 'rou')")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parser_collects_multiple_helpers_and_ignores_vrf_form(self) -> None:
        parsed = parse_running_config_sections(CONFIG)

        self.assertEqual(
            parsed.dhcp_helpers,
            [
                {
                    "interface_name": "GigabitEthernet0/0",
                    "helper_ip": "10.10.10.10",
                },
                {
                    "interface_name": "GigabitEthernet0/0",
                    "helper_ip": "10.10.10.11",
                },
                {
                    "interface_name": "GigabitEthernet0/1",
                    "helper_ip": "10.20.20.20",
                },
            ],
        )

    def test_sync_persists_helpers_idempotently_and_removes_absent_rows(self) -> None:
        for _ in range(2):
            summary = sync_device_state(self.db_path, "r1", CONFIG)
            self.assertEqual(summary["dhcp_helpers"], 3)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT i.interface_name, h.helper_ip, h.sync_status
                FROM t03_router_iface_helper AS h
                JOIN t02_interface_name AS i ON i.iface_id = h.iface_id
                ORDER BY i.interface_name, h.helper_ip
                """
            ).fetchall()
        self.assertEqual(
            rows,
            [
                ("GigabitEthernet0/0", "10.10.10.10", "synchronized"),
                ("GigabitEthernet0/0", "10.10.10.11", "synchronized"),
                ("GigabitEthernet0/1", "10.20.20.20", "synchronized"),
            ],
        )

        sync_device_state(
            self.db_path,
            "r1",
            CONFIG.replace(" ip helper-address 10.10.10.11\n", ""),
        )
        with sqlite3.connect(self.db_path) as conn:
            helpers = [
                row[0]
                for row in conn.execute(
                    "SELECT helper_ip FROM t03_router_iface_helper ORDER BY helper_ip"
                )
            ]
        self.assertEqual(helpers, ["10.10.10.10", "10.20.20.20"])

    def test_safe_preserves_pending_helper_and_force_replaces_it(self) -> None:
        sync_device_state(self.db_path, "r1", CONFIG)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE t03_router_iface_helper SET sync_status = 'pending_apply' "
                "WHERE helper_ip = '10.10.10.10'"
            )

        changed = CONFIG.replace("10.10.10.10", "10.10.10.99")
        result = sync_device_state(self.db_path, "r1", changed, mode="safe")
        self.assertIn("dhcp_helpers", result["conflicts"])
        with sqlite3.connect(self.db_path) as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM t03_router_iface_helper "
                    "WHERE helper_ip = '10.10.10.10'"
                ).fetchone()
            )

        sync_device_state(self.db_path, "r1", changed, mode="force_device_state")
        with sqlite3.connect(self.db_path) as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM t03_router_iface_helper "
                    "WHERE helper_ip = '10.10.10.99'"
                ).fetchone()
            )


if __name__ == "__main__":
    unittest.main()
