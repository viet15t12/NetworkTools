from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR / "features"))

from acl import delete_acl, get_acl_binding_catalog, get_acls, save_acl, save_acl_bindings
from dhcp import (
    add_dhcp_helper_address,
    add_dhcp_pool,
    delete_dhcp_pool,
    get_dhcp_helper_addresses,
    get_dhcp_pools,
    update_dhcp_pool,
)
from dhcp.worker import render_dhcp_template


class DatabaseAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _dict_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]


class DhcpAclPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "device_network.db"
        scripts = [
            APP_DIR / "infrastructure" / "database" / "schemas" / "device_network" / name
            for name in ("01_core_devices.sql", "02_interface_router_l3.sql", "03_dhcp_helper.sql", "05_security_nat.sql")
        ]
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for script in scripts:
                conn.executescript(script.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO t01_devices (host) VALUES ('10.0.0.1')")
            conn.execute(
                "INSERT INTO t02_interface_name (host, interface_name) VALUES ('10.0.0.1', 'GigabitEthernet0/0')"
            )
            conn.execute(
                "INSERT INTO t02_interface_name (host, interface_name) VALUES ('10.0.0.1', 'GigabitEthernet0/1')"
            )
            conn.commit()
        self.db = DatabaseAdapter(self.path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_dhcp_pool_round_trip_and_cisco_action_bits(self) -> None:
        self.assertTrue(add_dhcp_pool(
            self.db, "10.0.0.1", "LAN", "192.168.10.0", "/24",
            "192.168.10.1", "8.8.8.8", "1",
        ))
        row = get_dhcp_pools(self.db, "10.0.0.1")[0]
        self.assertEqual(row["subnetmask"], "255.255.255.0")
        self.assertTrue(update_dhcp_pool(
            self.db, row["dhcp_id"], "LAN", "192.168.10.0", "255.255.255.0",
            "192.168.10.254", "1.1.1.1 8.8.8.8", "1",
        ))
        changed = get_dhcp_pools(self.db, "10.0.0.1")[0]
        self.assertEqual(changed["action_Cfg"], "110")

        self.assertTrue(update_dhcp_pool(
            self.db, changed["dhcp_id"], "LAN20", "192.168.20.0", "/24",
            "192.168.20.1", "8.8.8.8", "2 12 30",
        ))
        with closing(self.db._connect()) as conn:
            states = conn.execute("SELECT pool, sync_status FROM t03_dhcp_pool ORDER BY dhcp_id").fetchall()
        self.assertEqual(
            [(row[0], row[1]) for row in states],
            [("LAN20", "pending_apply")],
        )

    def test_unchanged_pool_edit_is_a_database_no_op(self) -> None:
        self.assertTrue(add_dhcp_pool(
            self.db, "10.0.0.1", "LAN", "192.168.10.0", "/24",
            "192.168.10.1", "8.8.8.8", "1",
        ))
        row = get_dhcp_pools(self.db, "10.0.0.1")[0]
        with closing(self.db._connect()) as conn:
            conn.execute(
                "UPDATE t03_dhcp_pool SET sync_status = 'synchronized', "
                "action_Cfg = '000' WHERE dhcp_id = ?",
                (row["dhcp_id"],),
            )
            conn.commit()

        self.assertTrue(update_dhcp_pool(
            self.db, row["dhcp_id"], "LAN", "192.168.10.0", "/24",
            "192.168.10.1", "8.8.8.8", "1",
        ))
        unchanged = get_dhcp_pools(self.db, "10.0.0.1")[0]
        self.assertEqual(unchanged["sync_status"], "synchronized")
        self.assertEqual(unchanged["action_Cfg"], "000")

    def test_pool_template_skips_unchanged_optional_commands(self) -> None:
        rendered = render_dhcp_template(
            "cisco_ios",
            {
                "config": [{
                    "pools": [{
                        "name": "LAN",
                        "network": "192.168.10.0",
                        "subnet_mask": "255.255.255.0",
                        "default_gateway": "192.168.10.1",
                        "dns_server": "8.8.8.8",
                        "lease": "1",
                        "push_default": False,
                        "push_dns": False,
                        "push_lease": False,
                        "state": "setup",
                    }]
                }]
            },
        )
        self.assertNotIn("no default-router", rendered)
        self.assertNotIn("no dns-server", rendered)
        self.assertNotIn("no lease", rendered)
        self.assertNotIn("default-router 192.168.10.1", rendered)
        self.assertNotIn("dns-server 8.8.8.8", rendered)

        removal = render_dhcp_template(
            "cisco_ios",
            {
                "config": [{
                    "pools": [{
                        "name": "LAN",
                        "network": "192.168.10.0",
                        "subnet_mask": "255.255.255.0",
                        "default_gateway": None,
                        "dns_server": None,
                        "lease": "1",
                        "push_default": True,
                        "push_dns": True,
                        "push_lease": False,
                        "state": "setup",
                    }]
                }]
            },
        )
        self.assertIn("no default-router", removal)
        self.assertIn("no dns-server", removal)
        self.assertNotIn("no lease", removal)

    def test_helper_load_uses_runtime_interface_column(self) -> None:
        with closing(self.db._connect()) as conn:
            iface_id = conn.execute("SELECT iface_id FROM t02_interface_name").fetchone()[0]
        self.assertTrue(add_dhcp_helper_address(self.db, iface_id, "10.10.10.10"))
        loaded = get_dhcp_helper_addresses(self.db, "10.0.0.1")
        self.assertEqual(loaded[0]["interface_name"], "GigabitEthernet0/0")

    def test_deleting_unpushed_dhcp_pool_cancels_pending_push(self) -> None:
        self.assertTrue(add_dhcp_pool(
            self.db, "10.0.0.1", "LOCAL_ONLY", "192.168.30.0", "/24",
            "192.168.30.1", "8.8.8.8", "1",
        ))
        pool_id = get_dhcp_pools(self.db, "10.0.0.1")[0]["dhcp_id"]

        self.assertTrue(delete_dhcp_pool(self.db, pool_id))

        with closing(self.db._connect()) as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM t03_dhcp_pool WHERE dhcp_id = ?", (pool_id,)
            ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_acl_round_trip_edit_cancel_contract_and_soft_delete(self) -> None:
        with closing(self.db._connect()) as conn:
            iface_id = conn.execute("SELECT iface_id FROM t02_interface_name").fetchone()[0]
        payload = {
            "acl_id": 0, "host": "10.0.0.1", "acl_name": "EDGE_IN",
            "acl_type": "Standard", "description": "edge filter",
            "rules": [{"sequence": 10, "action": "permit", "source": "192.168.1.0", "wildcard": "0.0.0.255"}],
            "binding": {"iface_id": iface_id, "direction": "in"},
        }
        self.assertTrue(save_acl(self.db, payload))
        loaded = get_acls(self.db, "10.0.0.1", "Standard")
        self.assertEqual(loaded[0]["acl_type"], "standard")
        self.assertEqual(loaded[0]["bindings"][0]["interface_name"], "GigabitEthernet0/0")
        acl_id = loaded[0]["Acl_id"]

        payload.update({"acl_id": acl_id, "description": "changed", "description_only": True})
        self.assertTrue(save_acl(self.db, payload))
        with closing(self.db._connect()) as conn:
            rule_count = conn.execute(
                "SELECT COUNT(*) FROM t05_standard_acl_rules WHERE acl_id = ?", (acl_id,)
            ).fetchone()[0]
        self.assertEqual(rule_count, 1)

        payload.update({
            "description_only": False, "rules_changed": False, "binding_changed": True,
            "binding": {"iface_id": iface_id, "direction": "out"},
        })
        self.assertTrue(save_acl(self.db, payload))
        with closing(self.db._connect()) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM t05_standard_acl_rules WHERE acl_id = ?", (acl_id,)
            ).fetchone()[0], 1)

        self.assertTrue(delete_acl(self.db, acl_id))
        with closing(self.db._connect()) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM t05_ACL_DB WHERE Acl_id = ?", (acl_id,)
            ).fetchone()[0], 0)

        self.assertTrue(save_acl(self.db, {
            "host": "10.0.0.1", "acl_name": "EDGE_IN", "acl_type": "standard",
            "rules": [{"sequence": 20, "action": "deny", "source": "any"}],
        }))
        recreated = get_acls(self.db, "10.0.0.1", "standard")
        self.assertEqual(len(recreated), 1)
        self.assertEqual(recreated[0]["rules"][0]["sequence"], 20)

    def test_invalid_cisco_values_do_not_write(self) -> None:
        self.assertFalse(add_dhcp_pool(
            self.db, "10.0.0.1", "BAD POOL", "192.168.10.3", "/24", "192.168.10.1", "bad", "1",
        ))
        self.assertFalse(save_acl(self.db, {
            "host": "10.0.0.1", "acl_name": "BAD ACL", "acl_type": "extended",
            "rules": [{"sequence": 10, "action": "permit", "source": "999.1.1.1", "destination": "any"}],
        }))
        with closing(self.db._connect()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t03_dhcp_pool").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM t05_ACL_DB").fetchone()[0], 0)

    def test_extended_acl_normalizes_bare_port_to_cisco_eq_syntax(self) -> None:
        self.assertTrue(save_acl(self.db, {
            "host": "10.0.0.1", "acl_name": "WEB_IN", "acl_type": "extended",
            "rules": [{
                "sequence": 10, "action": "permit", "protocol": "tcp",
                "source": "any", "destination": "192.168.10.10", "dst_port": "443",
            }],
        }))
        row = get_acls(self.db, "10.0.0.1", "Extended")[0]["rules"][0]
        self.assertEqual(row["dst_port"], "eq 443")

    def test_acl_timeouts_follow_dynamic_minutes_and_reflexive_seconds_ranges(self) -> None:
        base_rule = {
            "sequence": 10,
            "action": "permit",
            "protocol": "ip",
            "source": "any",
            "destination": "any",
        }
        dynamic_rule = dict(base_rule, dynamic_name="DYNAMIC_EDGE", timeout_seconds=300)
        reflexive_rule = dict(base_rule, reflect_name="REFLECT_EDGE", timeout_seconds=30)

        self.assertTrue(save_acl(self.db, {
            "host": "10.0.0.1",
            "acl_name": "DYNAMIC_EDGE",
            "acl_type": "dynamic",
            "rules": [dynamic_rule],
        }))
        self.assertTrue(save_acl(self.db, {
            "host": "10.0.0.1",
            "acl_name": "REFLECT_EDGE",
            "acl_type": "reflexive",
            "rules": [reflexive_rule],
        }))
        self.assertEqual(
            get_acls(self.db, "10.0.0.1", "dynamic")[0]["rules"][0]["timeout_seconds"],
            300,
        )
        self.assertEqual(
            get_acls(self.db, "10.0.0.1", "reflexive")[0]["rules"][0]["timeout_seconds"],
            30,
        )

        self.assertFalse(save_acl(self.db, {
            "host": "10.0.0.1",
            "acl_name": "DYNAMIC_TOO_SHORT",
            "acl_type": "dynamic",
            "rules": [dict(dynamic_rule, timeout_seconds=59)],
        }))
        self.assertFalse(save_acl(self.db, {
            "host": "10.0.0.1",
            "acl_name": "REFLEXIVE_TOO_SHORT",
            "acl_type": "reflexive",
            "rules": [dict(reflexive_rule, timeout_seconds=29)],
        }))

    def test_one_acl_can_bind_to_multiple_interfaces(self) -> None:
        with closing(self.db._connect()) as conn:
            iface_ids = [row[0] for row in conn.execute(
                "SELECT iface_id FROM t02_interface_name ORDER BY iface_id"
            ).fetchall()]
        self.assertTrue(save_acl(self.db, {
            "host": "10.0.0.1", "acl_name": "MULTI_IN", "acl_type": "standard",
            "rules": [{"sequence": 10, "action": "permit", "source": "any"}],
        }))
        acl_id = get_acl_binding_catalog(self.db, "10.0.0.1")[0]["Acl_id"]
        self.assertTrue(save_acl_bindings(self.db, acl_id, [
                {"iface_id": iface_ids[0], "direction": "in"},
                {"iface_id": iface_ids[1], "direction": "in"},
                {"iface_id": iface_ids[1], "direction": "out"},
        ]))
        loaded = get_acls(self.db, "10.0.0.1", "standard")[0]
        self.assertEqual(len(loaded["bindings"]), 3)
        self.assertEqual(
            {(item["interface_name"], item["direction"]) for item in loaded["bindings"]},
            {("GigabitEthernet0/0", "in"), ("GigabitEthernet0/1", "in"), ("GigabitEthernet0/1", "out")},
        )
        self.assertTrue(save_acl(self.db, {
            "acl_id": acl_id, "host": "10.0.0.1", "acl_name": "MULTI_IN", "acl_type": "standard",
            "rules_changed": True,
            "rules": [{"sequence": 20, "action": "deny", "source": "any"}],
        }))
        self.assertEqual(len(get_acl_binding_catalog(self.db, "10.0.0.1")[0]["bindings"]), 3)


if __name__ == "__main__":
    unittest.main()
