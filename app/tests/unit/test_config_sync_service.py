from __future__ import annotations

import unittest
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from features.config_sync import ConfigSyncService
from features.devices import DeviceRepository
from scripts.build_databases import combine_sql


class ConfigSyncServiceTests(unittest.TestCase):
    def test_changed_router_snapshot_updates_real_application_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "device_network.db"
            schema_dir = (
                Path(__file__).resolve().parents[2]
                / "infrastructure"
                / "database"
                / "schemas"
                / "device_network"
            )
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executescript(combine_sql(schema_dir))
                connection.execute(
                    "INSERT INTO t01_devices(host, role) VALUES (?, ?)",
                    ("10.2.3.1", "rou"),
                )
                connection.commit()

            repository = DeviceRepository(db_path)
            service = ConfigSyncService(db_path, repository.get_role)
            result = service.sync_committed_snapshot(
                "10.2.3.1",
                """hostname R1
interface GigabitEthernet0/0
 ip address 192.0.2.1 255.255.255.0
 no shutdown
!
router ospf 1
 router-id 1.1.1.1
 network 192.0.2.0 0.0.0.255 area 0
!
""",
                "",
                {"changed": True, "commitId": "d" * 40},
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["interfaces"], 1)
            self.assertEqual(result["summary"]["ospf_processes"], 1)
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT device_name FROM t01_devices WHERE host = ?",
                        ("10.2.3.1",),
                    ).fetchone()[0],
                    "R1",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT ip_address FROM t02_interface_name WHERE host = ?",
                        ("10.2.3.1",),
                    ).fetchone()[0],
                    "192.0.2.1",
                )

    def test_changed_router_snapshot_runs_sync_pipeline(self) -> None:
        calls: list[tuple[str, str, str, str | None]] = []

        def synchronize(db_path: str, host: str, config: str, brief: str | None):
            calls.append((db_path, host, config, brief))
            return {"interfaces": 2, "ospf_processes": 1}

        service = ConfigSyncService("device.db", lambda _host: "ROU", synchronize)
        result = service.sync_committed_snapshot(
            "10.2.3.1",
            "hostname router\n",
            "GigabitEthernet0/0 up up\n",
            {"changed": True, "commitId": "a" * 40},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["attempted"])
        self.assertEqual(result["reason"], "synchronized")
        self.assertEqual(result["summary"]["interfaces"], 2)
        self.assertEqual(len(calls), 1)

    def test_non_router_and_unchanged_router_are_skipped(self) -> None:
        def must_not_run(*_args):
            raise AssertionError("sync pipeline must not run")

        switch_service = ConfigSyncService("device.db", lambda _host: "sw3", must_not_run)
        switch_result = switch_service.sync_committed_snapshot(
            "switch-1", "hostname switch\n", "", {"changed": True}
        )
        self.assertEqual(switch_result["reason"], "not-router")
        self.assertFalse(switch_result["attempted"])

        router_service = ConfigSyncService("device.db", lambda _host: "rou", must_not_run)
        unchanged_result = router_service.sync_committed_snapshot(
            "router-1", "hostname router\n", "", {"changed": False}
        )
        self.assertEqual(unchanged_result["reason"], "unchanged")
        self.assertFalse(unchanged_result["attempted"])

    def test_manual_sync_runs_pipeline_for_unchanged_snapshot(self) -> None:
        calls = []

        def synchronize(*args):
            calls.append(args)
            return {"interfaces": 1}

        service = ConfigSyncService("device.db", lambda _host: "rou", synchronize)
        result = service.sync_manual_snapshot(
            "router-1", "hostname router\n", "", {"changed": False, "commitId": "abc"}
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "manual-synchronized")
        self.assertEqual(len(calls), 1)

    def test_router_interface_brief_syncs_when_running_config_is_unchanged(self) -> None:
        calls = []

        def synchronize(*args):
            calls.append(args)
            return {"interfaces": 1}

        service = ConfigSyncService("device.db", lambda _host: "rou", synchronize)
        result = service.sync_committed_snapshot(
            "router-1",
            "hostname router\n",
            "GigabitEthernet0/0 unassigned YES unset up up\n",
            {"changed": False, "commitId": "abc"},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["attempted"])
        self.assertEqual(result["reason"], "synchronized")
        self.assertEqual(len(calls), 1)

    def test_switch_operational_state_syncs_even_when_running_config_is_unchanged(self) -> None:
        calls = []

        def sync_switch(db_path, host, snapshot, mode):
            calls.append((db_path, host, snapshot, mode))
            return {"vlans": 2, "conflicts": []}

        service = ConfigSyncService(
            "device.db",
            lambda _host: "sw2",
            switch_synchronizer=sync_switch,
        )
        result = service.sync_committed_snapshot(
            "switch-1",
            "hostname switch\n",
            "",
            {"changed": False, "commitId": "abc"},
            switch_state={"vlan_brief": "1 default active"},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["attempted"])
        self.assertEqual(result["summary"]["vlans"], 2)
        self.assertEqual(calls[0][3], "safe")

    def test_sw3_passes_running_config_to_switch_fhrp_sync(self) -> None:
        calls = []

        def sync_switch(db_path, host, snapshot, mode):
            calls.append((db_path, host, snapshot, mode))
            return {"fhrp_members": 1, "conflicts": []}

        service = ConfigSyncService(
            "device.db",
            lambda _host: "sw3",
            switch_synchronizer=sync_switch,
        )
        running_config = "interface Vlan20\n standby 20 ip 192.0.2.1\n!\n"
        result = service.sync_committed_snapshot(
            "switch-1",
            running_config,
            "",
            {"changed": True, "commitId": "abc"},
            switch_state={"vlan_brief": "20 USERS active"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0][2]["running_config"], running_config)

    def test_sync_failure_does_not_hide_committed_snapshot_context(self) -> None:
        def fail(*_args):
            raise RuntimeError("database is locked")

        service = ConfigSyncService("device.db", lambda _host: "rou", fail)
        result = service.sync_committed_snapshot(
            "router-1", "hostname router\n", "", {"changed": True, "commitId": "b" * 40}
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["attempted"])
        self.assertEqual(result["commitId"], "b" * 40)
        self.assertIn("database is locked", result["message"])

    def test_role_lookup_failure_is_reported_without_running_sync(self) -> None:
        def role_lookup(_host: str):
            raise RuntimeError("inventory unavailable")

        service = ConfigSyncService("device.db", role_lookup)
        result = service.sync_committed_snapshot(
            "router-1", "hostname router\n", "", {"changed": True, "commitId": "c" * 40}
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["attempted"])
        self.assertEqual(result["reason"], "role-lookup-failed")
        self.assertIn("inventory unavailable", result["message"])


if __name__ == "__main__":
    unittest.main()
