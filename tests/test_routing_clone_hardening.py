from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from features.routing.clone_service import RoutingCloneService
from features.routing.ospf import get_ospf_routing, save_ospf_routing
from scripts.build_databases import combine_sql
from tests.test_database_routing_contract import _DatabaseAdapter


class RoutingCloneHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device.db"
        schema_dir = (
            Path(__file__).resolve().parents[1]
            / "infrastructure"
            / "database"
            / "schemas"
            / "device_network"
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(combine_sql(schema_dir))
            conn.execute("INSERT INTO t01_devices(host, connection_status) VALUES ('r1', 'connected')")
            conn.execute("INSERT INTO t01_devices(host, connection_status) VALUES ('r2', 'connected')")
            conn.execute("INSERT INTO t01_devices(host, connection_status) VALUES ('r3', 'connected')")
            conn.execute(
                "INSERT INTO t02_interface_name(host, interface_name, sync_status) VALUES ('r1', 'Gi0/0', 'synchronized')"
            )
            conn.execute(
                "INSERT INTO t02_interface_name(host, interface_name, sync_status) VALUES ('r2', 'Gi0/0', 'synchronized')"
            )
            conn.commit()
        self.db = _DatabaseAdapter(self.db_path)
        self.assertTrue(
            save_ospf_routing(
                self.db,
                "r1",
                [{
                    "process_id": 1,
                    "router_id": "1.1.1.1",
                    "interface_settings": [{"interface_name": "Gi0/0", "area": 0}],
                }],
            )
        )
        self.source_id = get_ospf_routing(self.db, "r1")["processes"][0]["ospf_id"]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_source_is_excluded_and_router_id_is_optional(self) -> None:
        service = RoutingCloneService(self.db)
        self.assertEqual(service.connected_hosts("r1"), ["r2", "r3"])
        result = service.clone_targets(
            "r1", [{"host": "r2", "processId": 20, "routerId": ""}], "ospf", self.source_id
        )
        self.assertTrue(result["ok"], result)
        self.assertIsNone(get_ospf_routing(self.db, "r2")["processes"][0]["router_id"])

    def test_missing_interface_blocks_or_process_only_skips_settings(self) -> None:
        service = RoutingCloneService(self.db)
        blocked = service.clone_targets(
            "r1", [{"host": "r3", "processId": 30}], "ospf", self.source_id
        )
        self.assertEqual(blocked["failed"][0]["code"], "MISSING_INTERFACE")
        allowed = service.clone_targets(
            "r1",
            [{"host": "r3", "processId": 30, "processOnly": True}],
            "ospf",
            self.source_id,
        )
        self.assertTrue(allowed["ok"], allowed)
        self.assertEqual(
            get_ospf_routing(self.db, "r3")["processes"][0]["interface_settings"],
            [],
        )

    def test_clone_does_not_modify_an_unrelated_target_process(self) -> None:
        self.assertTrue(save_ospf_routing(self.db, "r2", [{"process_id": 99, "router_id": "9.9.9.9"}]))
        before = get_ospf_routing(self.db, "r2")["processes"][0]
        result = RoutingCloneService(self.db).clone_targets(
            "r1", [{"host": "r2", "processId": 20}], "ospf", self.source_id
        )
        self.assertTrue(result["ok"], result)
        processes = get_ospf_routing(self.db, "r2")["processes"]
        untouched = next(row for row in processes if row["process_id"] == 99)
        self.assertEqual(untouched["ospf_id"], before["ospf_id"])
        self.assertEqual(untouched["router_id"], "9.9.9.9")

    def test_batch_validation_reports_each_target_from_stable_source(self) -> None:
        results = RoutingCloneService(self.db).validate_targets(
            "r1",
            "ospf",
            self.source_id,
            [
                {"host": "r2", "processId": 20},
                {"host": "r3", "processId": 30},
            ],
        )
        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["matchedInterfaces"], ["Gi0/0"])
        self.assertEqual(results[1]["code"], "MISSING_INTERFACE")
        self.assertEqual(results[1]["missingInterfaces"], ["Gi0/0"])

    def test_invalid_router_id_and_stale_source_have_structured_codes(self) -> None:
        invalid = RoutingCloneService(self.db).clone_targets(
            "r1",
            [{"host": "r2", "processId": 20, "routerId": "999.1.1.1"}],
            "ospf",
            self.source_id,
        )
        self.assertEqual(invalid["failed"][0]["code"], "INVALID_ROUTER_ID")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM t04_ospf_processes WHERE ospf_id = ?",
                (self.source_id,),
            )
            conn.commit()
        stale = RoutingCloneService(self.db).clone_targets(
            "r1",
            [{"host": "r2", "processId": 20}],
            "ospf",
            self.source_id,
        )
        self.assertEqual(
            stale["failed"][0]["code"], "SOURCE_PROCESS_NOT_FOUND"
        )


if __name__ == "__main__":
    unittest.main()
