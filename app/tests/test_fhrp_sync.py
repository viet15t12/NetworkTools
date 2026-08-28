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


FHRP_CONFIG = """
interface GigabitEthernet0/0
 ip address 192.0.2.2 255.255.255.0
 standby version 2
 standby 10 ip 192.0.2.1
 standby 10 priority 120
 standby 10 preempt delay minimum 15 reload 30
 standby 10 timers msec 500 msec 1500
 standby 10 track 7 25
!
interface GigabitEthernet0/1
 ip address 198.51.100.2 255.255.255.0
 vrrp 20 ip 198.51.100.1
 vrrp 20 priority 110
 vrrp 20 preempt
 vrrp 20 timers advertise msec 750
 vrrp 20 track GigabitEthernet0/2 decrement 30
!
interface GigabitEthernet0/2
 ip address 203.0.113.2 255.255.255.0
 glbp 30 ip 203.0.113.1
 glbp 30 priority 105
 glbp 30 preempt
 glbp 30 load-balancing weighted
 glbp 30 weighting 120 lower 90 upper 110
 glbp 30 weighting track 9 decrement 20
 glbp 30 forwarder preempt delay minimum 12
!
"""


class FhrpSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(combine_sql(SCHEMA_DIR))
            conn.execute("INSERT INTO t01_devices(host, role) VALUES ('r1', 'rou')")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parser_reads_hsrp_vrrp_and_glbp_interface_state(self) -> None:
        parsed = parse_running_config_sections(FHRP_CONFIG)
        self.assertEqual(len(parsed.fhrp_members), 3)
        by_protocol = {row["protocol"]: row for row in parsed.fhrp_members}
        self.assertEqual(by_protocol["hsrp"]["priority"], 120)
        self.assertEqual(
            by_protocol["hsrp"]["options"]["preempt_delay_reload_sec"], 30
        )
        self.assertEqual(by_protocol["vrrp"]["options"]["advertisement_ms"], 750)
        self.assertEqual(by_protocol["glbp"]["options"]["load_balancing"], "weighted")
        self.assertEqual(by_protocol["glbp"]["tracks"][0]["decrement_value"], 20)

    def test_parser_uses_ios_defaults_when_commands_are_omitted(self) -> None:
        parsed = parse_running_config_sections(
            """
interface GigabitEthernet0/0
 standby 1 ip 192.0.2.1
 vrrp 2 ip 192.0.2.254
!
"""
        )
        by_protocol = {row["protocol"]: row for row in parsed.fhrp_members}
        self.assertEqual(by_protocol["hsrp"]["options"]["version"], 1)
        self.assertEqual(by_protocol["hsrp"]["preempt"], 0)
        self.assertEqual(by_protocol["vrrp"]["preempt"], 1)

    def test_sync_is_idempotent_and_persists_protocol_options(self) -> None:
        for _ in range(2):
            result = sync_device_state(self.db_path, "r1", FHRP_CONFIG)
            self.assertEqual(result["fhrp_members"], 3)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t08_fhrp_members").fetchone()[0],
                3,
            )
            self.assertEqual(
                set(
                    row[0]
                    for row in conn.execute(
                        "SELECT DISTINCT sync_status FROM t08_fhrp_members"
                    )
                ),
                {"synchronized"},
            )
            glbp = conn.execute(
                "SELECT load_balancing, weighting_max FROM t08_glbp_options"
            ).fetchone()
            self.assertEqual(tuple(glbp), ("weighted", 120))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t08_fhrp_tracks").fetchone()[0],
                3,
            )

    def test_safe_preserves_pending_and_force_replaces_device_state(self) -> None:
        sync_device_state(self.db_path, "r1", FHRP_CONFIG)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE t08_fhrp_members SET sync_status = 'pending_apply' "
                "WHERE member_id = (SELECT MIN(member_id) FROM t08_fhrp_members)"
            )
        changed = FHRP_CONFIG.replace("192.0.2.1", "192.0.2.254", 1)
        result = sync_device_state(self.db_path, "r1", changed, mode="safe")
        self.assertIn("fhrp", result["conflicts"])
        with sqlite3.connect(self.db_path) as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM t08_fhrp_groups WHERE virtual_ip = '192.0.2.1'"
                ).fetchone()
            )
        sync_device_state(self.db_path, "r1", changed, mode="force_device_state")
        with sqlite3.connect(self.db_path) as conn:
            self.assertIsNotNone(
                conn.execute(
                    "SELECT 1 FROM t08_fhrp_groups WHERE virtual_ip = '192.0.2.254'"
                ).fetchone()
            )

    def test_sync_removes_only_target_host_from_shared_group(self) -> None:
        sync_device_state(self.db_path, "r1", FHRP_CONFIG)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO t01_devices(host, role) VALUES ('r2', 'rou')")
        sync_device_state(self.db_path, "r2", FHRP_CONFIG)
        sync_device_state(self.db_path, "r1", "", mode="force_device_state")
        with sqlite3.connect(self.db_path) as conn:
            hosts = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT host FROM t08_fhrp_members ORDER BY host"
                )
            ]
            self.assertEqual(hosts, ["r2"])
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t08_fhrp_groups").fetchone()[0],
                3,
            )


if __name__ == "__main__":
    unittest.main()
