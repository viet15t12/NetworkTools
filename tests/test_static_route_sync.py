from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from features.devices.sync_state import (
    parse_running_config_sections,
    sync_device_state,
)
from scripts.build_databases import combine_sql


SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "infrastructure"
    / "database"
    / "schemas"
    / "device_network"
)


class StaticRouteSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device.db"
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(combine_sql(SCHEMA_DIR))
            conn.execute("INSERT INTO t01_devices(host, role) VALUES ('r1', 'rou')")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parse_simple_static_default_and_unsupported_routes(self) -> None:
        parsed = parse_running_config_sections(
            """
ip default-gateway 192.0.2.254
ip route 10.10.0.0 255.255.0.0 192.0.2.1
ip route 10.20.0.0 255.255.0.0 192.0.2.2 10
ip route 0.0.0.0 0.0.0.0 192.0.2.254
ip route 10.30.0.0 255.255.0.0 GigabitEthernet0/0
"""
        )
        self.assertEqual([row["ad"] for row in parsed.static_routes], [1, 10])
        self.assertEqual(parsed.default_routes[0]["next_hop_ip"], "192.0.2.254")

    def test_parse_multiple_default_routes(self) -> None:
        parsed = parse_running_config_sections(
            """
ip route 0.0.0.0 0.0.0.0 192.0.2.1
ip route 0.0.0.0 0.0.0.0 198.51.100.1
"""
        )

        self.assertEqual(
            [row["next_hop_ip"] for row in parsed.default_routes],
            ["192.0.2.1", "198.51.100.1"],
        )
        self.assertNotIn(
            "MULTIPLE_DEFAULT_ROUTES_UNSUPPORTED",
            [row.get("code") for row in parsed.unsupported_routes],
        )
        self.assertEqual(
            {row["code"] for row in parsed.unsupported_routes},
            {"NON_IPV4_ROUTE_UNSUPPORTED"},
        )

    def test_sync_is_idempotent_and_removes_observed_routes(self) -> None:
        config = """
ip route 10.10.0.0 255.255.0.0 192.0.2.1
ip route 0.0.0.0 0.0.0.0 192.0.2.254
"""
        for _ in range(2):
            result = sync_device_state(self.db_path, "r1", config)
            self.assertEqual(result["static_routes"], 1)
            self.assertEqual(result["default_routes"], 1)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t04_static_routes").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t04_static_default_routes").fetchone()[0], 1)
        sync_device_state(self.db_path, "r1", "")
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t04_static_routes").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t04_static_default_routes").fetchone()[0], 0)

    def test_safe_mode_preserves_pending_and_force_replaces_it(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO t04_static_routes
                    (host, network, subnet_mask, next_hop, sync_status)
                VALUES ('r1', '10.99.0.0', '255.255.0.0', '192.0.2.9', 'pending_apply')
                """
            )
        config = "ip route 10.10.0.0 255.255.0.0 192.0.2.1"
        result = sync_device_state(self.db_path, "r1", config, mode="safe")
        self.assertIn("static_routes", result["conflicts"])
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(
                conn.execute("SELECT network FROM t04_static_routes").fetchone()[0],
                "10.99.0.0",
            )
        preview = sync_device_state(self.db_path, "r1", config, mode="preview")
        self.assertIn("static_routes", preview["conflicts"])
        sync_device_state(self.db_path, "r1", config, mode="force_device_state")
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(
                conn.execute("SELECT network FROM t04_static_routes").fetchone()[0],
                "10.10.0.0",
            )

    def test_interface_inventory_is_derived_from_collected_state_and_reconciled(self) -> None:
        first_config = """
interface GigabitEthernet0/0
 description configured uplink
 ip address 192.0.2.1 255.255.255.0
!
"""
        first_brief = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.0.2.1       YES manual up                    up
GigabitEthernet0/1     unassigned      YES unset  down                  down
"""
        sync_device_state(self.db_path, "r1", first_config, first_brief)
        with sqlite3.connect(self.db_path) as conn:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT interface_name FROM t02_interface_name WHERE host = 'r1'"
                )
            }
        self.assertEqual(names, {"GigabitEthernet0/0", "GigabitEthernet0/1"})

        second_brief = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/1     unassigned      YES unset  up                    up
"""
        sync_device_state(self.db_path, "r1", "", second_brief)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT interface_name, sync_status FROM t02_interface_name WHERE host = 'r1'"
            ).fetchall()
        self.assertEqual(rows, [("GigabitEthernet0/1", "synchronized")])

    def test_parse_and_sync_classic_eigrp_idempotently(self) -> None:
        config = """
router eigrp 100
 eigrp router-id 2.2.2.2
 network 10.0.0.0 0.255.255.255
 passive-interface default
 no passive-interface GigabitEthernet0/0
 variance 2
 maximum-paths 4
 distance eigrp 90 170
 redistribute static metric 100000 10 255 1 1500 route-map STATIC
!
router eigrp CAMPUS
 address-family ipv4 autonomous-system 200
!
"""
        parsed = parse_running_config_sections(config)
        process = parsed.eigrp_processes[100]
        self.assertEqual(process["router_id"], "2.2.2.2")
        self.assertEqual(process["variance"], 2)
        self.assertEqual(process["redistribute"][0]["metric_mtu"], 1500)
        self.assertEqual(
            parsed.unsupported_routing[0]["code"],
            "NAMED_EIGRP_UNSUPPORTED",
        )
        for _ in range(2):
            summary = sync_device_state(self.db_path, "r1", config)
            self.assertEqual(summary["eigrp_processes"], 1)
            self.assertEqual(summary["unsupported_routing"], 1)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t04_eigrp_processes").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT sync_status FROM t04_eigrp_processes").fetchone()[0],
                "synchronized",
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t04_eigrp_networks").fetchone()[0],
                1,
            )

    def test_safe_eigrp_sync_preserves_pending_process(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO t04_eigrp_processes(host, as_number, sync_status) VALUES ('r1', 99, 'pending_apply')"
            )
        result = sync_device_state(
            self.db_path,
            "r1",
            "router eigrp 100\n network 10.0.0.0\n!",
        )
        self.assertIn("eigrp", result["conflicts"])
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(
                conn.execute("SELECT as_number FROM t04_eigrp_processes").fetchone()[0],
                99,
            )

    def test_static_module_sync_does_not_modify_ospf(self) -> None:
        from features.devices.sync_state import sync_static_routes

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO t04_ospf_processes(host, process_id, router_id, sync_status)
                VALUES ('r1', 1, '1.1.1.1', 'synchronized')
                """
            )
            sync_static_routes(
                conn,
                "r1",
                [{
                    "network": "10.10.0.0",
                    "subnet_mask": "255.255.0.0",
                    "next_hop": "192.0.2.1",
                    "ad": 1,
                }],
            )
            conn.commit()
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT router_id FROM t04_ospf_processes WHERE host = 'r1'"
                ).fetchone()[0],
                "1.1.1.1",
            )


if __name__ == "__main__":
    unittest.main()
