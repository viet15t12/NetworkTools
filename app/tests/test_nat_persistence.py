from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR / "features"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from nat import (
    add_nat_acl,
    add_nat_dynamic_pool,
    add_nat_interface,
    add_nat_pat_rule,
    add_nat_route_map_entry,
    add_nat_static_entry,
    delete_nat_acl,
    delete_nat_dynamic_pool,
    delete_nat_interface,
    delete_nat_pat_rule,
    delete_nat_route_map_entry,
    delete_nat_static_entry,
    get_nat_acls,
    get_nat_acl_names,
    get_nat_dynamic_pools,
    get_nat_interfaces,
    get_nat_pat_rules,
    get_nat_route_map_entries,
    get_nat_route_map_names,
    get_nat_static_entries,
)
from scripts.build_databases import combine_sql


class _Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


class NatPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        schema = combine_sql(APP_DIR / "infrastructure" / "database" / "schemas" / "device_network")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(schema)
            connection.execute(
                """
                INSERT INTO t01_devices
                    (host, device_name, method, portnumber, username, password, os, role, connection_status, dev)
                VALUES ('r1', 'Router 1', 'SSH', 22, 'user', 'pass', 'cisco_ios', 'router', 'connected', 1);
                """
            )
            connection.commit()
        self.db = _Database(self.db_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _sync_status(self, table: str, id_column: str, row_id: int) -> str:
        with closing(sqlite3.connect(self.db_path)) as connection:
            return str(connection.execute(
                f"SELECT sync_status FROM {table} WHERE {id_column} = ?",
                (row_id,),
            ).fetchone()[0])

    def test_static_save_load_and_soft_delete(self) -> None:
        self.assertTrue(add_nat_static_entry(self.db, "r1", "10.0.0.10", "203.0.113.10", "TCP", "80", "8080"))
        rows = get_nat_static_entries(self.db, "r1")
        self.assertEqual((rows[0]["inside_local"], rows[0]["inside_global"]), ("10.0.0.10", "203.0.113.10"))
        row_id = rows[0]["nat_static_id"]
        self.assertEqual(self._sync_status("t05_nat_static_mappings", "id", row_id), "pending_apply")
        self.assertTrue(delete_nat_static_entry(self.db, row_id))
        self.assertEqual(get_nat_static_entries(self.db, "r1"), [])
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM t05_nat_static_mappings WHERE id = ?", (row_id,)
            ).fetchone())

    def test_static_rejects_invalid_addresses_protocols_and_ports(self) -> None:
        self.assertFalse(add_nat_static_entry(
            self.db, "r1", "999.0.0.1", "203.0.113.10", "", "", ""
        ))
        self.assertFalse(add_nat_static_entry(
            self.db, "r1", "10.0.0.10", "203.0.113.10", "icmp", "", ""
        ))
        self.assertFalse(add_nat_static_entry(
            self.db, "r1", "10.0.0.10", "203.0.113.10", "tcp", "0", "80"
        ))
        self.assertFalse(add_nat_static_entry(
            self.db, "r1", "10.0.0.10", "203.0.113.10", "udp", "53", "70000"
        ))

    def test_deleting_synchronized_nat_still_queues_device_removal(self) -> None:
        self.assertTrue(add_nat_static_entry(
            self.db, "r1", "10.0.0.20", "203.0.113.20", "TCP", "80", "8080"
        ))
        row_id = get_nat_static_entries(self.db, "r1")[0]["nat_static_id"]
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE t05_nat_static_mappings SET sync_status = 'synchronized' WHERE id = ?",
                (row_id,),
            )
            connection.commit()

        self.assertTrue(delete_nat_static_entry(self.db, row_id))

        self.assertEqual(
            self._sync_status("t05_nat_static_mappings", "id", row_id),
            "pending_delete",
        )

    def test_interface_save_load_delete_and_reactivate(self) -> None:
        self.assertTrue(add_nat_interface(self.db, "r1", "GigabitEthernet0/0", "inside"))
        row = get_nat_interfaces(self.db, "r1")[0]
        self.assertEqual((row["interface_name"], row["direction"]), ("GigabitEthernet0/0", "inside"))
        row_id = row["nat_intf_id"]
        self.assertTrue(delete_nat_interface(self.db, row_id))
        self.assertTrue(add_nat_interface(self.db, "r1", "GigabitEthernet0/0", "outside"))
        row = get_nat_interfaces(self.db, "r1")[0]
        self.assertEqual(
            (row["direction"], row["sync_status"]),
            ("outside", "pending_apply"),
        )

    def test_dynamic_pool_persists_acl_relationship(self) -> None:
        self.assertTrue(add_nat_dynamic_pool(
            self.db, "r1", "PUBLIC", "203.0.113.1", "203.0.113.10", "255.255.255.0", "NAT_ACL"
        ))
        row = get_nat_dynamic_pools(self.db, "r1")[0]
        self.assertEqual(row["acl_name"], "NAT_ACL")
        self.assertEqual(row["nat_name"], "dynamic_r1")
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE t05_NAT_DB SET sync_status = 'pending_delete' WHERE nat_id = ?",
                (row["nat_id"],),
            )
            connection.commit()
        self.assertTrue(add_nat_dynamic_pool(
            self.db, "r1", "PUBLIC", "203.0.113.2", "203.0.113.11",
            "255.255.255.0", "NAT_ACL",
        ))
        self.assertEqual(
            self._sync_status("t05_NAT_DB", "nat_id", row["nat_id"]),
            "pending_apply",
        )
        row_id = row["nat_dynamic_id"]
        self.assertTrue(delete_nat_dynamic_pool(self.db, row_id))
        self.assertEqual(get_nat_dynamic_pools(self.db, "r1"), [])
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM t05_nat_pools WHERE pool_id = ?", (row_id,)
            ).fetchone())

    def test_dynamic_pool_rejects_invalid_or_reversed_ranges(self) -> None:
        self.assertFalse(add_nat_dynamic_pool(
            self.db, "r1", "BAD_IP", "203.0.113.999", "203.0.113.10",
            "255.255.255.0", "",
        ))
        self.assertFalse(add_nat_dynamic_pool(
            self.db, "r1", "REVERSED", "203.0.113.10", "203.0.113.1",
            "255.255.255.0", "",
        ))
        self.assertFalse(add_nat_dynamic_pool(
            self.db, "r1", "BAD_MASK", "203.0.113.1", "203.0.113.10",
            "255.0.255.0", "",
        ))

    def test_pat_interface_and_pool_round_trip(self) -> None:
        self.assertTrue(add_nat_dynamic_pool(
            self.db, "r1", "PUBLIC", "203.0.113.1", "203.0.113.10", "255.255.255.0", ""
        ))
        self.assertTrue(add_nat_pat_rule(self.db, "r1", "NAT_ACL", "Interface", "GigabitEthernet0/1", True))
        self.assertTrue(add_nat_pat_rule(self.db, "r1", "NAT_ACL", "Pool", "PUBLIC", True))
        rows = get_nat_pat_rules(self.db, "r1")
        self.assertEqual({(row["source_type"], row["source_value"]) for row in rows}, {
            ("Interface", "GigabitEthernet0/1"), ("Pool", "PUBLIC")
        })
        self.assertEqual(
            {row["nat_name"] for row in rows},
            {"pat_r1", "dynamic_r1"},
        )
        self.assertTrue(all(row["description"] == "" for row in rows))
        for row in rows:
            self.assertTrue(delete_nat_pat_rule(self.db, row["nat_pat_id"]))
        self.assertEqual(get_nat_pat_rules(self.db, "r1"), [])

    def test_acl_load_is_flat_for_qml_and_rule_delete_is_soft(self) -> None:
        self.assertTrue(add_nat_acl(self.db, "r1", "NAT_ACL", "permit", "10.0.0.0", "0.0.0.255"))
        self.assertEqual(get_nat_acl_names(self.db, "r1"), ["NAT_ACL"])
        row = get_nat_acls(self.db, "r1")[0]
        self.assertEqual((row["action"], row["source_network"], row["wildcard"]), (
            "permit", "10.0.0.0", "0.0.0.255"
        ))
        self.assertEqual((row["description"], row["sequence"]), ("", 10))
        self.assertTrue(add_nat_acl(
            self.db, "r1", "NAT_ACL", "deny", "10.0.1.0", "0.0.0.255"
        ))
        self.assertEqual(
            [item["sequence"] for item in get_nat_acls(self.db, "r1")],
            [10, 20],
        )
        rule_id = row["rule_id"]
        for item in get_nat_acls(self.db, "r1"):
            self.assertTrue(delete_nat_acl(self.db, item["rule_id"]))
        self.assertEqual(get_nat_acls(self.db, "r1"), [])
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM t05_nat_standard_acl_rules WHERE id = ?", (rule_id,)
            ).fetchone())

    def test_legacy_nullable_acl_roles_are_normalized_for_qml(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection:
            acl_id = connection.execute(
                """
                INSERT INTO t05_NAT_ACL_DB
                    (acl_name, acl_type, host, description, sync_status)
                VALUES ('LEGACY_NAT_ACL', 'standard', 'r1', NULL, 'synchronized');
                """
            ).lastrowid
            connection.execute(
                """
                INSERT INTO t05_nat_standard_acl_rules
                    (nat_acl_id, sequence, action, source, wildcard, sync_status)
                VALUES (?, NULL, 'permit', '10.10.0.0', NULL, 'synchronized');
                """,
                (acl_id,),
            )
            connection.commit()

        row = get_nat_acls(self.db, "r1")[0]
        self.assertEqual(row["description"], "")
        self.assertEqual(row["wildcard"], "")
        self.assertIsInstance(row["sequence"], int)

    def test_nat_acl_accepts_host_and_any_sources(self) -> None:
        self.assertTrue(add_nat_acl(
            self.db, "r1", "NAT_HOSTS", "permit", "10.0.0.10", ""
        ))
        self.assertTrue(add_nat_acl(
            self.db, "r1", "NAT_ANY", "deny", "any", ""
        ))
        rows = get_nat_acls(self.db, "r1")
        self.assertEqual(
            {(row["acl_name"], row["source_network"], row["wildcard"]) for row in rows},
            {("NAT_HOSTS", "10.0.0.10", ""), ("NAT_ANY", "any", "")},
        )
        self.assertFalse(add_nat_acl(
            self.db, "r1", "NAT_BAD", "permit", "10.0.0.999", ""
        ))

    def test_route_map_save_load_soft_delete_and_reactivate(self) -> None:
        self.assertTrue(add_nat_acl(self.db, "r1", "NAT_ACL", "permit", "10.0.0.0", "0.0.0.255"))
        self.assertTrue(add_nat_route_map_entry(self.db, "r1", "NAT_EXEMPT", "test", 10, "permit", "NAT_ACL"))
        self.assertEqual(get_nat_route_map_names(self.db, "r1"), ["NAT_EXEMPT"])
        row = get_nat_route_map_entries(self.db, "r1")[0]
        self.assertEqual((row["nat_acl_name"], row["description"]), ("NAT_ACL", "test"))
        row_id = row["route_map_entry_id"]
        self.assertTrue(delete_nat_route_map_entry(self.db, row_id))
        self.assertEqual(get_nat_route_map_entries(self.db, "r1"), [])
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM t05_route_map_entries WHERE id = ?", (row_id,)
            ).fetchone())
        self.assertTrue(add_nat_route_map_entry(self.db, "r1", "NAT_EXEMPT", "updated", 10, "deny", "NAT_ACL"))
        row = get_nat_route_map_entries(self.db, "r1")[0]
        self.assertEqual((row["action"], row["description"]), ("deny", "updated"))

        self.assertFalse(add_nat_route_map_entry(
            self.db, "r1", "NAT_ZERO", "", 0, "permit", "",
        ))
        self.assertFalse(add_nat_route_map_entry(
            self.db, "r1", "NAT_NEGATIVE", "", -1, "permit", "",
        ))
        self.assertFalse(add_nat_route_map_entry(
            self.db, "r1", "NAT_TOO_LARGE", "", 65536, "permit", "",
        ))


if __name__ == "__main__":
    unittest.main()
