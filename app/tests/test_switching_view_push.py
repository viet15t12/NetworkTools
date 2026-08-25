from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from features.switching.view_push import SwitchingViewPushController  # noqa: E402
from features.switching import (  # noqa: E402
    delete_l2_trust_port,
    delete_l2_vlan_security,
    delete_static_mac,
    delete_stp_config,
    delete_vlan,
    save_vlan,
)
from scripts.build_databases import combine_sql  # noqa: E402


class FakeConnection:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.config_calls = 0

    def send_config_set(self, commands, **_kwargs):
        self.config_calls += 1
        self.commands.extend(commands)
        return "configuration accepted"


class FakeConnector:
    def __init__(self) -> None:
        self.connection = FakeConnection()


class FakeSwitchStateConnector(FakeConnector):
    def __init__(self, outputs, events=None) -> None:
        super().__init__()
        self.outputs = dict(outputs)
        self.events = events
        self.state_calls = []

    def collect_switch_state(self, state_keys=None):
        requested = tuple(self.outputs) if state_keys is None else tuple(state_keys)
        self.state_calls.append(requested)
        if self.events is not None:
            self.events.append("client")
        return {
            "ok": True,
            "outputs": {key: self.outputs[key] for key in requested},
        }


class DatabaseAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _routing_device_context(self, _host: str) -> dict[str, str]:
        return {
            "platform": "cisco_ios",
            "template_folder": "cisco_ios",
            "method": "SSH",
        }


class TestController(SwitchingViewPushController):
    __test__ = False

    def __init__(self, db, connector, connectors=None):
        super().__init__(db)
        self.connector = connector
        self.connectors = dict(connectors or {})

    def _session_provider_for_host(self, host):
        return lambda target: self.connectors.get(target, self.connector)


class SwitchingViewPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        schema = combine_sql(
            APP_DIR / "infrastructure" / "database" / "schemas" / "device_network"
        )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(schema)
            conn.execute(
                """
                INSERT INTO t01_devices(host, role, os, method, device_type)
                VALUES ('sw2.local', 'sw2', 'cisco_ios', 'SSH', 'switch');
                """
            )
            conn.executemany(
                """
                INSERT INTO t06_vlan_db(host, vlan_id, vlan_name, state)
                VALUES ('sw2.local', ?, ?, 'active');
                """,
                ((1, "default"), (10, "users")),
            )
            iface_id = conn.execute(
                """
                INSERT INTO t06_interface_l2(host, if_name, mode)
                VALUES ('sw2.local', 'GigabitEthernet0/1', 'access');
                """
            ).lastrowid
            conn.execute(
                "INSERT INTO t06_iface_access(iface_id, access_vlan) VALUES (?, 10);",
                (iface_id,),
            )
            conn.execute(
                """
                INSERT INTO t06_iface_stp(iface_id, portfast, bpduguard)
                VALUES (?, 'enabled', 'enabled');
                """,
                (iface_id,),
            )
            conn.execute(
                """
                INSERT INTO t06_iface_port_security(iface_id, enabled, max_mac, sticky)
                VALUES (?, 1, 2, 1);
                """,
                (iface_id,),
            )
            conn.execute(
                """
                INSERT INTO t06_etherchannel(
                    host, po_number, protocol, mode, member_ports, description
                ) VALUES (
                    'sw2.local', 1, 'lacp', 'active',
                    'GigabitEthernet0/1', 'Uplink'
                );
                """
            )
            conn.execute(
                """
                INSERT INTO t06_stp_config(host, vlan_id, stp_mode, root_role)
                VALUES ('sw2.local', 10, 'rapid-pvst', 'primary');
                """
            )
            conn.execute(
                """
                INSERT INTO t06_security_l2(
                    host, vlan_id, dhcp_snooping, dai_enabled
                ) VALUES ('sw2.local', 10, 1, 1);
                """
            )
            conn.execute(
                """
                INSERT INTO t06_dhcp_trust_ports(host, if_name)
                VALUES ('sw2.local', 'GigabitEthernet0/1');
                """
            )
            conn.execute(
                """
                INSERT INTO t06_iface_mac_table(
                    iface_id, mac_addr, vlan_id, mac_type
                ) VALUES (?, '0011.2233.4455', 10, 'static');
                """,
                (iface_id,),
            )
            domain_id = conn.execute(
                """
                INSERT INTO t09_vtp_domains(domain_name, version)
                VALUES ('LAB', 2);
                """
            ).lastrowid
            switch_id = conn.execute(
                """
                INSERT INTO t09_vtp_switches(vtp_domain_id, host, pruning)
                VALUES (?, 'sw2.local', 1);
                """,
                (domain_id,),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO t09_vtp_database_modes(vtp_switch_id, database_type, mode)
                VALUES (?, 'vlan', 'server');
                """,
                (switch_id,),
            )
            conn.commit()
        self.db = DatabaseAdapter(self.db_path)
        self.connector = FakeConnector()
        self.controller = TestController(self.db, self.connector)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_combines_layer2_modules_without_opening_a_session(self) -> None:
        pending = self.controller.pending_state("sw2.local", "all")
        self.assertTrue(pending["success"], pending)
        self.assertTrue(pending["hasPending"], pending)
        preview = self.controller.preview("sw2.local", "all")
        self.assertTrue(preview["ok"], preview)
        self.assertTrue(preview["success"], preview)
        self.assertTrue(all(task["success"] == "pending_apply" for task in preview["tasks"]))
        self.assertIn("vlan 10", preview["commands"])
        self.assertIn("switchport access vlan 10", preview["commands"])
        self.assertIn("channel-group 1 mode active", preview["commands"])
        self.assertIn("spanning-tree mode rapid-pvst", preview["commands"])
        self.assertIn("spanning-tree portfast", preview["commands"])
        self.assertNotIn("spanning-tree portfast trunk", preview["commands"])
        self.assertIn("vtp domain LAB", preview["commands"])
        self.assertIn("ip dhcp snooping vlan 10", preview["commands"])
        self.assertIn("switchport port-security maximum 2", preview["commands"])
        self.assertEqual(self.connector.connection.commands, [])

    def test_post_push_restores_full_operational_pull_for_every_switch_tab(self) -> None:
        for module in (
            "all",
            "vlan",
            "svi",
            "interfaces",
            "etherchannel",
            "stp",
            "vtp",
            "l2_security",
            "port_security",
        ):
            with self.subTest(module=module):
                self.assertEqual(
                    self.controller.reconciliation_options(module),
                    {"switch_state_keys": None},
                )

    def test_successful_push_updates_success_and_a_change_becomes_pending(self) -> None:
        result = self.controller.push("sw2.local", "all")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["success"], result)
        self.assertTrue(all(item["success"] for item in result["report"]))
        self.assertIn("vlan 10", self.connector.connection.commands)
        self.assertEqual(self.connector.connection.config_calls, 1)
        self.assertFalse(self.controller.has_pending("sw2.local", "all"))
        with closing(self.db._connect()) as conn:
            for table in (
                "t06_vlan_db",
                "t06_interface_l2",
                "t06_iface_port_security",
                "t06_iface_mac_table",
                "t06_etherchannel",
                "t06_stp_config",
                "t06_security_l2",
                "t06_dhcp_trust_ports",
                "t09_vtp_switches",
            ):
                with self.subTest(table=table):
                    statuses = {
                        row["success"]
                        for row in conn.execute(f"SELECT success FROM {table};")
                    }
                    self.assertEqual(statuses, {"synchronized"})
            for table in ("t06_vlan_db", "t06_etherchannel"):
                presence = {
                    row["device_present"]
                    for row in conn.execute(
                        f"SELECT device_present FROM {table};"
                    )
                }
                self.assertEqual(presence, {1})

        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                UPDATE t06_vlan_db
                SET vlan_name = 'staff', success = 'pending_apply'
                WHERE host = 'sw2.local' AND vlan_id = 10;
                """
            )
            conn.commit()

        self.assertTrue(self.controller.has_pending("sw2.local", "vlan"))

    def test_port_channel_trunk_omits_physical_commands_and_sets_encapsulation_first(self) -> None:
        with closing(self.db._connect()) as conn:
            for table in (
                "t06_vlan_db",
                "t06_interface_l2",
                "t06_iface_port_security",
                "t06_iface_mac_table",
                "t06_etherchannel",
                "t06_stp_config",
                "t06_security_l2",
                "t06_dhcp_trust_ports",
                "t09_vtp_switches",
            ):
                conn.execute(f"UPDATE {table} SET success = 'synchronized';")
            iface_id = conn.execute(
                """
                INSERT INTO t06_interface_l2(
                    host, if_name, mode, speed, duplex, success
                ) VALUES (
                    'sw2.local', 'Port-channel3', 'trunk', 'auto', 'auto',
                    'pending_apply'
                );
                """
            ).lastrowid
            conn.execute(
                """
                INSERT INTO t06_iface_trunk(
                    iface_id, allowed_vlans, native_vlan, encapsulation
                ) VALUES (?, '10,20', 10, 'dot1q');
                """,
                (iface_id,),
            )
            conn.execute(
                """
                INSERT INTO t06_iface_stp(iface_id, portfast)
                VALUES (?, 'enabled');
                """,
                (iface_id,),
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "interfaces")

        self.assertTrue(preview["success"], preview)
        commands = preview["commands"].splitlines()
        self.assertNotIn(" speed auto", commands)
        self.assertNotIn(" duplex auto", commands)
        self.assertNotIn(" switchport mode access", commands)
        self.assertNotIn(" switchport access vlan 10", commands)
        encapsulation_index = commands.index(
            " switchport trunk encapsulation dot1q"
        )
        trunk_index = commands.index(" switchport mode trunk")
        self.assertLess(encapsulation_index, trunk_index)
        self.assertIn(" spanning-tree portfast trunk", commands)
        self.assertNotIn(" spanning-tree portfast", commands)

    def test_each_tab_pushes_only_changed_rows_from_its_own_module(self) -> None:
        self.assertTrue(self.controller.push("sw2.local", "all")["success"])
        self.connector.connection.commands.clear()

        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                UPDATE t06_vlan_db
                SET vlan_name = 'staff', success = 'pending_apply'
                WHERE host = 'sw2.local' AND vlan_id = 10;
                """
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "vlan")
        self.assertTrue(preview["success"], preview)
        self.assertEqual(len(preview["tasks"]), 1)
        self.assertEqual(preview["tasks"][0]["entity_key"], "vlan:10")
        self.assertNotIn("interface GigabitEthernet0/1", preview["commands"])
        self.assertNotIn("vtp domain", preview["commands"])

        pushed = self.controller.push("sw2.local", "vlan")
        self.assertTrue(pushed["success"], pushed)
        self.assertEqual(len(pushed["report"]), 1)
        self.assertEqual(pushed["report"][0]["entity"], "vlan:10")
        self.assertNotIn("interface GigabitEthernet0/1", self.connector.connection.commands)
        self.assertFalse(self.controller.has_pending("sw2.local", "vlan"))

    def test_vtp_client_cannot_save_or_push_local_vlan_configuration(self) -> None:
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                UPDATE t09_vtp_database_modes
                SET mode = 'client'
                WHERE vtp_switch_id = (
                    SELECT vtp_switch_id FROM t09_vtp_switches
                    WHERE host = 'sw2.local'
                );
                """
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "vlan")
        saved = save_vlan(
            self.db,
            "sw2.local",
            {"vlan_id": 20, "vlan_name": "voice", "state": "active"},
        )
        deleted = delete_vlan(self.db, "sw2.local", 2)

        self.assertTrue(preview["success"], preview)
        self.assertEqual(preview["tasks"], [])
        self.assertEqual(preview["commands"], "")
        self.assertFalse(saved["ok"], saved)
        self.assertIn("VTP client", saved["message"])
        self.assertFalse(deleted["ok"], deleted)
        self.assertIn("VTP client", deleted["message"])

    def test_vlan_push_reconciles_server_before_clients_in_same_vtp_domain(self) -> None:
        events = []
        client = FakeSwitchStateConnector(
            {
                "vtp_status": """VTP version running : 2
VTP Domain Name : LAB
VTP Operating Mode : Client
VTP Pruning Mode : Enabled
""",
                "vlan_brief": """VLAN Name Status Ports
1 default active
10 users active
20 voice active
""",
            },
            events,
        )
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                INSERT INTO t01_devices(host, role, os, method, device_type)
                VALUES ('sw3.local', 'sw2', 'cisco_ios', 'SSH', 'switch');
                """
            )
            switch_id = conn.execute(
                """
                INSERT INTO t09_vtp_switches(vtp_domain_id, host, pruning)
                SELECT vtp_domain_id, 'sw3.local', 1
                FROM t09_vtp_domains WHERE domain_name = 'LAB';
                """
            ).lastrowid
            conn.execute(
                """
                INSERT INTO t09_vtp_database_modes(
                    vtp_switch_id, database_type, mode
                ) VALUES (?, 'vlan', 'client');
                """,
                (switch_id,),
            )
            conn.execute(
                """
                INSERT INTO t06_vlan_db(
                    host, vlan_id, vlan_name, success, device_present
                ) VALUES ('sw3.local', 30, 'stale', 'synchronized', 1);
                """
            )
            conn.commit()

        def reconcile_server(host, connector, **_options):
            self.assertEqual(host, "sw2.local")
            self.assertIs(connector, self.connector)
            events.append("server")
            return {"ok": True, "message": "server synchronized"}

        self.db.reconcileViewPushSnapshot = reconcile_server
        controller = TestController(
            self.db,
            self.connector,
            {"sw3.local": client},
        )
        tasks = controller.collect_pending_tasks("sw2.local", "vlan")

        result = controller._push_and_reconcile(
            "sw2.local", "vlan", tasks, self.connector
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(events, ["server", "client"])
        self.assertEqual(
            client.state_calls, [("vtp_status", "vlan_brief")]
        )
        self.assertEqual(
            result["vtpClientReconciliation"]["success"], 1
        )
        with closing(self.db._connect()) as conn:
            vlans = conn.execute(
                """
                SELECT vlan_id, device_present
                FROM t06_vlan_db
                WHERE host = 'sw3.local'
                ORDER BY vlan_id;
                """
            ).fetchall()
        self.assertEqual(
            [(row["vlan_id"], row["device_present"]) for row in vlans],
            [(1, 1), (10, 1), (20, 1), (30, 0)],
        )

    def test_vtp_client_snapshot_is_rejected_when_device_reports_other_domain(self) -> None:
        client = FakeSwitchStateConnector(
            {
                "vtp_status": """VTP version running : 2
VTP Domain Name : OTHER
VTP Operating Mode : Client
VTP Pruning Mode : Disabled
""",
                "vlan_brief": "1 default active\n20 foreign active\n",
            }
        )

        with self.assertRaisesRegex(ValueError, "expected LAB"):
            self.controller._sync_vtp_client("sw3.local", "LAB", client)

    def test_synchronized_success_rows_are_not_rendered_or_reapplied(self) -> None:
        with closing(self.db._connect()) as conn:
            conn.execute(
                "UPDATE t06_vlan_db SET success = 'synchronized' WHERE host = 'sw2.local';"
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "vlan")

        self.assertTrue(preview["success"], preview)
        self.assertEqual(preview["tasks"], [])
        self.assertEqual(preview["commands"], "")

    def test_vlan_delete_push_uses_no_vlan_and_removes_database_row(self) -> None:
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                UPDATE t06_vlan_db
                SET success = 'pending_delete'
                WHERE host = 'sw2.local' AND vlan_id = 10;
                """
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "vlan")
        self.assertTrue(preview["success"], preview)
        delete_task = next(
            task for task in preview["tasks"] if task["entity_key"] == "vlan:10"
        )
        self.assertEqual(delete_task["success"], "pending_delete")
        self.assertEqual(delete_task["commands"], ["no vlan 10"])
        self.assertIn("no vlan 10", preview["commands"])

        pushed = self.controller.push("sw2.local", "vlan")
        self.assertTrue(pushed["success"], pushed)
        self.assertIn("no vlan 10", self.connector.connection.commands)
        with closing(self.db._connect()) as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM t06_vlan_db WHERE host = 'sw2.local' AND vlan_id = 10;"
            ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_svi_view_push_applies_routing_create_and_delete(self) -> None:
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                INSERT INTO t01_devices(host, role, os, method, device_type)
                VALUES ('sw3.local', 'sw3', 'cisco_ios', 'SSH', 'switch');
                """
            )
            conn.execute(
                """
                INSERT INTO t06_vlan_db(
                    host, vlan_id, vlan_name, state, success
                ) VALUES ('sw3.local', 20, 'users', 'active', 'synchronized');
                """
            )
            conn.execute(
                """
                INSERT INTO t06_switch_l3_config(host, ip_routing, sync_status)
                VALUES ('sw3.local', 1, 'pending_apply');
                """
            )
            svi_id = conn.execute(
                """
                INSERT INTO t06_svi_interface(
                    host, vlan_id, ip_address, subnet_mask, shutdown, sync_status
                ) VALUES (
                    'sw3.local', 20, '192.0.2.1', '255.255.255.0', 0,
                    'pending_apply'
                );
                """
            ).lastrowid
            conn.commit()

        preview = self.controller.preview("sw3.local", "svi")
        self.assertTrue(preview["success"], preview)
        self.assertEqual(len(preview["tasks"]), 2)
        self.assertIn("ip routing", preview["commands"])
        self.assertIn("interface Vlan20", preview["commands"])
        self.assertIn(" ip address 192.0.2.1 255.255.255.0", preview["commands"])
        self.assertIn(" no shutdown", preview["commands"])

        pushed = self.controller.push("sw3.local", "svi")
        self.assertTrue(pushed["success"], pushed)
        with closing(self.db._connect()) as conn:
            routing_status = conn.execute(
                "SELECT sync_status FROM t06_switch_l3_config WHERE host = 'sw3.local';"
            ).fetchone()[0]
            svi_status = conn.execute(
                "SELECT sync_status FROM t06_svi_interface WHERE id = ?;",
                (svi_id,),
            ).fetchone()[0]
            conn.execute(
                "UPDATE t06_svi_interface SET sync_status = 'pending_delete' WHERE id = ?;",
                (svi_id,),
            )
            conn.commit()
        self.assertEqual((routing_status, svi_status), ("synchronized", "synchronized"))

        delete_preview = self.controller.preview("sw3.local", "svi")
        self.assertEqual(len(delete_preview["tasks"]), 1)
        self.assertIn("no interface Vlan20", delete_preview["commands"])
        deleted = self.controller.push("sw3.local", "svi")
        self.assertTrue(deleted["success"], deleted)
        with closing(self.db._connect()) as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM t06_svi_interface WHERE id = ?;",
                (svi_id,),
            ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_etherchannel_delete_push_removes_members_and_database_row(self) -> None:
        self.assertTrue(self.controller.push("sw2.local", "all")["success"])
        self.connector.connection.commands.clear()
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                INSERT INTO t06_interface_l2(
                    host, if_name, mode, success
                ) VALUES (
                    'sw2.local', 'Port-channel1', 'trunk', 'synchronized'
                );
                """
            )
            conn.execute(
                """
                UPDATE t06_etherchannel
                SET success = 'pending_delete'
                WHERE host = 'sw2.local' AND po_number = 1;
                """
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "etherchannel")
        self.assertTrue(preview["success"], preview)
        self.assertEqual(len(preview["tasks"]), 1)
        self.assertEqual(preview["tasks"][0]["success"], "pending_delete")
        self.assertIn(" no channel-group", preview["commands"])
        self.assertNotIn(" no channel-group 1", preview["commands"])
        self.assertIn("no interface Port-channel1", preview["commands"])
        self.assertNotIn(" channel-group 1 mode active", preview["commands"])

        pushed = self.controller.push("sw2.local", "etherchannel")
        self.assertTrue(pushed["success"], pushed)
        self.assertIn(" no channel-group", self.connector.connection.commands)
        self.assertNotIn(" no channel-group 1", self.connector.connection.commands)
        self.assertIn("no interface Port-channel1", self.connector.connection.commands)
        with closing(self.db._connect()) as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM t06_etherchannel WHERE host = 'sw2.local';"
            ).fetchone()[0]
            remaining_interface = conn.execute(
                """
                SELECT COUNT(*) FROM t06_interface_l2
                WHERE host = 'sw2.local' AND if_name = 'Port-channel1';
                """
            ).fetchone()[0]
        self.assertEqual(remaining, 0)
        self.assertEqual(remaining_interface, 0)

    def test_port_security_disable_uses_success_lifecycle_and_no_command(self) -> None:
        self.assertTrue(self.controller.push("sw2.local", "all")["success"])
        self.connector.connection.commands.clear()
        with closing(self.db._connect()) as conn:
            conn.execute(
                """
                UPDATE t06_iface_port_security
                SET enabled = 0, sync_status = 'pending_apply',
                    success = 'pending_apply'
                WHERE iface_id = (
                    SELECT id FROM t06_interface_l2
                    WHERE host = 'sw2.local' AND if_name = 'GigabitEthernet0/1'
                );
                """
            )
            conn.commit()

        preview = self.controller.preview("sw2.local", "port_security")
        self.assertTrue(preview["success"], preview)
        self.assertEqual(len(preview["tasks"]), 1)
        self.assertIn("no switchport port-security", preview["commands"])
        pushed = self.controller.push("sw2.local", "port_security")
        self.assertTrue(pushed["success"], pushed)
        with closing(self.db._connect()) as conn:
            row = conn.execute(
                "SELECT enabled, sync_status, success FROM t06_iface_port_security;"
            ).fetchone()
        self.assertEqual(tuple(row), (0, "synchronized", "synchronized"))

    def test_failed_device_output_does_not_mark_payload(self) -> None:
        self.connector.connection.send_config_set = (
            lambda _commands, **_kwargs: "% Invalid input detected"
        )
        task = self.controller.collect_pending_tasks("sw2.local", "vlan")[0]
        result = self.controller.push_tasks("sw2.local", "vlan", [task])
        self.assertFalse(result["ok"])
        self.assertFalse(result["success"])
        self.assertFalse(result["report"][0]["success"])
        with closing(self.db._connect()) as conn:
            row = conn.execute(
                "SELECT success FROM t06_vlan_db WHERE vlan_id = 1;"
            ).fetchone()
        self.assertEqual(row["success"], "pending_apply")

    def test_policy_deletes_send_no_commands_and_remove_rows_after_push(self) -> None:
        with closing(self.db._connect()) as conn:
            stp_id = conn.execute("SELECT id FROM t06_stp_config;").fetchone()[0]
            policy_id = conn.execute("SELECT id FROM t06_security_l2;").fetchone()[0]
            trust_id = conn.execute("SELECT id FROM t06_dhcp_trust_ports;").fetchone()[0]
            static_id = conn.execute(
                "SELECT id FROM t06_iface_mac_table WHERE mac_type = 'static';"
            ).fetchone()[0]

        self.assertTrue(delete_stp_config(self.db, "sw2.local", stp_id)["ok"])
        self.assertTrue(
            delete_l2_vlan_security(self.db, "sw2.local", policy_id)["ok"]
        )
        self.assertTrue(
            delete_l2_trust_port(self.db, "sw2.local", trust_id)["ok"]
        )
        self.assertTrue(delete_static_mac(self.db, "sw2.local", static_id)["ok"])

        preview = self.controller.preview("sw2.local", "all")
        self.assertIn("no spanning-tree vlan 10 priority", preview["commands"])
        self.assertIn(" no ip dhcp snooping trust", preview["commands"])
        self.assertIn("no mac address-table static", preview["commands"])
        pushed = self.controller.push("sw2.local", "all")
        self.assertTrue(pushed["success"], pushed)
        with closing(self.db._connect()) as conn:
            for table in (
                "t06_stp_config",
                "t06_security_l2",
                "t06_dhcp_trust_ports",
                "t06_iface_mac_table",
            ):
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0],
                    0,
                    table,
                )


if __name__ == "__main__":
    unittest.main()
