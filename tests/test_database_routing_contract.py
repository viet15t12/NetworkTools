from __future__ import annotations

import sqlite3
import tempfile
import unittest
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR / "features"))

from features.routing.eigrp import get_eigrp_routing, save_eigrp_routing
from features.routing.ospf import get_ospf_routing, save_ospf_routing
from features.routing import dispatcher as routing_dispatcher_module
from features.routing.ospf.schema import ensure_schema as ensure_ospf_schema
from features.routing.clone_service import RoutingCloneService
from core.database.conversion import ConversionMixin
from core.database.routing_slots import RoutingSlotsMixin
from scripts.build_databases import combine_sql


class _DatabaseAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.error = ""

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return list(value or [])

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value or {})

    @staticmethod
    def _dict_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        return None if value in (None, "") else int(value)

    @staticmethod
    def _int_or_zero(value: Any) -> int:
        return 0 if value in (None, "") else int(value)

    @staticmethod
    def _bool_int(value: Any) -> int:
        return int(bool(value))

    @staticmethod
    def _str_or_none(value: Any) -> str | None:
        text = "" if value is None else str(value).strip()
        return text or None

    def _set_last_routing_error(self, value: str) -> None:
        self.error = value


class RoutingDatabaseContractTests(unittest.TestCase):
    def test_ospf_schema_upgrade_adds_action_mask_to_legacy_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "CREATE TABLE t04_ospf_processes "
                    "(ospf_id INTEGER PRIMARY KEY, process_id INTEGER)"
                )
                changes = ensure_ospf_schema(connection)
                columns = {
                    row[1]: row for row in connection.execute(
                        "PRAGMA table_info(t04_ospf_processes)"
                    )
                }
            self.assertEqual(changes, ["t04_ospf_processes.action_Cfg"])
            self.assertEqual(columns["action_Cfg"][4], "'1111'")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        schema = combine_sql(APP_DIR / "infrastructure" / "database" / "schemas" / "device_network")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            connection.execute("INSERT INTO t01_devices (host) VALUES ('r1')")
            connection.execute("INSERT INTO t01_devices (host, connection_status) VALUES ('r2', 'connected')")
            connection.execute("INSERT INTO t01_devices (host, connection_status) VALUES ('r3', 'connected')")
            connection.execute(
                "INSERT INTO t02_interface_name (host, interface_name) VALUES ('r1', 'GigabitEthernet0/0')"
            )
            connection.execute(
                "INSERT INTO t02_interface_name (host, interface_name) VALUES ('r2', 'GigabitEthernet0/0')"
            )
            connection.execute(
                "INSERT INTO t02_interface_name (host, interface_name) VALUES ('r3', 'GigabitEthernet0/0')"
            )
            connection.commit()
        self.db = _DatabaseAdapter(self.db_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_ospf_save_load_and_repeat_do_not_duplicate_interface(self) -> None:
        payload = [{"process_id": 1, "router_id": "1.1.1.1", "interface_settings": [{
            "interface_name": "GigabitEthernet0/0", "area": 0, "cost": 10,
            "priority": 2, "hello_interval": 10, "dead_interval": 40,
            "bfd": True, "auth_key": "secret",
        }]}]
        self.assertTrue(save_ospf_routing(self.db, "r1", payload), self.db.error)
        loaded = get_ospf_routing(self.db, "r1")
        payload[0]["ospf_id"] = loaded["processes"][0]["ospf_id"]
        self.assertTrue(save_ospf_routing(self.db, "r1", payload), self.db.error)
        loaded = get_ospf_routing(self.db, "r1")
        interface = loaded["processes"][0]["interface_settings"][0]
        self.assertEqual(interface["interface_name"], "GigabitEthernet0/0")
        self.assertEqual(interface["priority"], 2)
        self.assertEqual(interface["auth_key"], "secret")
        with closing(self.db._connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM t04_router_iface_ospf").fetchone()[0], 1)

    def test_ospf_rejects_duplicate_process_ids_without_mutating_database(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{"process_id": 1}]))
        before = get_ospf_routing(self.db, "r1")["processes"]

        self.assertFalse(save_ospf_routing(
            self.db, "r1", [{"process_id": 2}, {"process_id": 2}]
        ))

        self.assertIn("Duplicate OSPF Process ID 2", self.db.error)
        self.assertEqual(get_ospf_routing(self.db, "r1")["processes"], before)

    def test_ospf_accepts_qml_new_process_database_id_zero(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "ospf_id": 0,
            "process_id": "10",
            "networks": [],
        }]), self.db.error)

        loaded = get_ospf_routing(self.db, "r1")["processes"]
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["process_id"], 10)

    def test_ospf_rejects_integer_outside_sqlite_range_without_mutating_database(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 10,
            "tuning": {"max_lsa": 1000},
        }]), self.db.error)
        before = get_ospf_routing(self.db, "r1")["processes"]

        self.assertFalse(save_ospf_routing(self.db, "r1", [{
            "process_id": 10,
            "tuning": {"max_lsa": 1 << 63},
        }]))
        self.assertIn("max lsa must be between", self.db.error)
        self.assertEqual(get_ospf_routing(self.db, "r1")["processes"], before)

    def test_ospf_process_id_only_update_does_not_archive_active_row(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 10,
            "router_id": "1.1.1.1",
        }]), self.db.error)

        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 10,
            "router_id": "2.2.2.2",
        }]), self.db.error)

        loaded = get_ospf_routing(self.db, "r1")["processes"]
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["router_id"], "2.2.2.2")
        self.assertNotEqual(loaded[0]["sync_status"], "pending_delete")

    def test_ospf_action_mask_only_selects_changed_process_commands(self) -> None:
        payload = [{
            "process_id": 10,
            "router_id": "1.1.1.1",
            "reference_bandwidth": 1000,
            "passive_default": False,
            "default_originate": False,
            "tuning": {"maximum_paths": 4},
        }]
        self.assertTrue(save_ospf_routing(self.db, "r1", payload), self.db.error)
        loaded = get_ospf_routing(self.db, "r1")["processes"][0]
        payload[0]["ospf_id"] = loaded["ospf_id"]
        with closing(self.db._connect()) as connection:
            connection.execute(
                "UPDATE t04_ospf_processes "
                "SET sync_status = 'synchronized', action_Cfg = '0000'"
            )
            connection.execute(
                "UPDATE t04_ospf_tuning SET sync_status = 'synchronized'"
            )
            connection.commit()

        payload[0]["tuning"] = {"maximum_paths": 8}
        self.assertTrue(save_ospf_routing(self.db, "r1", payload), self.db.error)
        with closing(self.db._connect()) as connection:
            row = connection.execute(
                "SELECT action_Cfg FROM t04_ospf_processes WHERE ospf_id = ?",
                (loaded["ospf_id"],),
            ).fetchone()
        self.assertEqual(row["action_Cfg"], "0000")
        previous_path = routing_dispatcher_module.DB_PATH
        try:
            routing_dispatcher_module.DB_PATH = str(self.db_path)
            task = routing_dispatcher_module.routing_dispatcher(
                "r1", "ospf", dry_run=True
            )[0]
        finally:
            routing_dispatcher_module.DB_PATH = previous_path
        config = task["config"][0]
        self.assertIsNone(config["router_id"])
        self.assertIsNone(config["reference_bandwidth"])
        self.assertIsNone(config["passive_default"])
        self.assertIsNone(config["default_originate"])

        payload[0]["router_id"] = "2.2.2.2"
        self.assertTrue(save_ospf_routing(self.db, "r1", payload), self.db.error)
        with closing(self.db._connect()) as connection:
            row = connection.execute(
                "SELECT action_Cfg FROM t04_ospf_processes WHERE ospf_id = ?",
                (loaded["ospf_id"],),
            ).fetchone()
        self.assertEqual(row["action_Cfg"], "1000")
        previous_path = routing_dispatcher_module.DB_PATH
        try:
            routing_dispatcher_module.DB_PATH = str(self.db_path)
            task = routing_dispatcher_module.routing_dispatcher(
                "r1", "ospf", dry_run=True
            )[0]
        finally:
            routing_dispatcher_module.DB_PATH = previous_path
        config = task["config"][0]
        self.assertEqual(config["router_id"], "2.2.2.2")
        self.assertIsNone(config["reference_bandwidth"])
        self.assertIsNone(config["passive_default"])
        self.assertIsNone(config["default_originate"])

    def test_ospf_rejects_unconvertible_child_rows_without_data_loss(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 1,
            "areas": [{"area_id": 0, "area_type": "normal"}],
        }]))
        loaded = get_ospf_routing(self.db, "r1")["processes"][0]

        self.assertFalse(save_ospf_routing(self.db, "r1", [{
            "ospf_id": loaded["ospf_id"],
            "process_id": 1,
            "areas": [object()],
        }]))

        self.assertIn("could not be converted from the QML payload", self.db.error)
        self.assertEqual(len(get_ospf_routing(self.db, "r1")["processes"][0]["areas"]), 1)

    def test_eigrp_save_load_and_repeat_do_not_duplicate_interface(self) -> None:
        payload = [{"as_number": 100, "router_id": "2.2.2.2", "interface_settings": [{
            "interface_name": "GigabitEthernet0/0", "bandwidth": 100000,
            "split_horizon": True, "bfd": True,
        }]}]
        self.assertTrue(save_eigrp_routing(self.db, "r1", payload))
        loaded = get_eigrp_routing(self.db, "r1")
        payload[0]["eigrp_id"] = loaded["processes"][0]["eigrp_id"]
        self.assertTrue(save_eigrp_routing(self.db, "r1", payload))
        loaded = get_eigrp_routing(self.db, "r1")
        self.assertEqual(loaded["processes"][0]["interface_settings"][0]["interface_name"], "GigabitEthernet0/0")
        with closing(self.db._connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM t04_router_iface_eigrp").fetchone()[0], 1)

    def test_clone_ospf_process_to_connected_host_marks_rows_pending(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 1,
            "router_id": "1.1.1.1",
            "networks": [{"network": "10.0.0.0", "wildcard": "0.0.0.255", "area": 0}],
        }]))

        result = RoutingCloneService(self.db).clone("r1", "r2", "ospf", 0, 20)

        self.assertTrue(result["ok"], result)
        loaded = get_ospf_routing(self.db, "r2")["processes"][0]
        self.assertEqual(loaded["process_id"], 20)
        self.assertIsNone(loaded["router_id"])
        self.assertEqual(loaded["sync_status"], "pending_apply")
        self.assertEqual(loaded["networks"][0]["sync_status"], "pending_apply")

    def test_clone_process_to_multiple_hosts_reports_each_result(self) -> None:
        self.assertTrue(save_eigrp_routing(self.db, "r1", [{
            "as_number": 100,
            "router_id": "1.1.1.1",
            "networks": [{"network": "10.0.0.0", "wildcard": "0.0.0.255"}],
        }]))
        self.assertTrue(save_eigrp_routing(self.db, "r3", [{"as_number": 200}]))

        result = RoutingCloneService(self.db).clone_many(
            "r1", ["r2", "r3"], "eigrp", 0, 200
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["successful"], ["r2"])
        self.assertEqual(result["failed"][0]["host"], "r3")
        self.assertIn("already exists", result["failed"][0]["reason"])
        self.assertEqual(get_eigrp_routing(self.db, "r2")["processes"][0]["as_number"], 200)

    def test_clone_slot_unwraps_qjsvalue_host_array(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{"process_id": 1}]))

        class FakeQjsValue:
            def toVariant(self):
                return ["r2", "r3"]

        class Bridge(ConversionMixin, RoutingSlotsMixin, _DatabaseAdapter):
            pass

        result = Bridge(self.db_path).cloneRoutingProcesses(
            "r1", FakeQjsValue(), "ospf", 0, 30
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["successful"], ["r2", "r3"])

    def test_clone_targets_uses_independent_process_and_router_ids(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r1", [{
            "process_id": 1, "router_id": "1.1.1.1"
        }]))

        source_id = get_ospf_routing(self.db, "r1")["processes"][0]["ospf_id"]
        result = RoutingCloneService(self.db).clone_targets(
            "r1",
            [
                {"host": "r2", "processId": 20, "routerId": "2.2.2.2"},
                {"host": "r3", "processId": 30, "routerId": "3.3.3.3"},
            ],
            "ospf",
            source_id,
        )

        self.assertTrue(result["ok"], result)
        r2 = get_ospf_routing(self.db, "r2")["processes"][0]
        r3 = get_ospf_routing(self.db, "r3")["processes"][0]
        self.assertEqual((r2["process_id"], r2["router_id"]), (20, "2.2.2.2"))
        self.assertEqual((r3["process_id"], r3["router_id"]), (30, "3.3.3.3"))


if __name__ == "__main__":
    unittest.main()
