"""Domain, persistence and command regressions for Router Interface."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

from features.devices.sync import parse_interface_block, sync_interfaces
from features.interfaces.collector import collect_interface_tasks
from features.interfaces.commands import render_interface_commands
from features.interfaces.models import canonical_interface_name
from features.interfaces.push_state import mark_interface_task_applied
from features.interfaces.repository import delete_router_interface
from features.interfaces.service import InterfaceService
from features.interfaces.view_push import InterfaceViewPushController


APP_DIR = Path(__file__).resolve().parents[1]


class _Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _dict_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _bool_int(value: Any) -> int:
        if isinstance(value, str):
            return int(value.strip().lower() in {"1", "true", "yes", "on"})
        return int(bool(value))

    @staticmethod
    def _routing_device_context(_host: str) -> dict[str, str]:
        return {
            "platform": "cisco_ios",
            "template_folder": "cisco_ios",
            "method": "SSH",
        }


class RouterInterfaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "device_network.db"
        schema_dir = (
            APP_DIR / "infrastructure" / "database" / "schemas" / "device_network"
        )
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            for name in ("01_core_devices.sql", "02_interface_router_l3.sql"):
                connection.executescript(
                    (schema_dir / name).read_text(encoding="utf-8")
                )
            connection.execute(
                "INSERT INTO t01_devices(host, role, os) VALUES (?, 'rou', 'cisco')",
                ("10.0.0.1",),
            )
            connection.execute(
                "INSERT INTO t02_interface_name(host, interface_name, sync_status) "
                "VALUES (?, ?, 'synchronized')",
                ("10.0.0.1", "GigabitEthernet0/0"),
            )
            connection.commit()
        self.db = _Database(self.path)
        self.service = InterfaceService(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_name_normalization_and_backend_physical_policy(self) -> None:
        self.assertEqual(canonical_interface_name(" gi 0/0 "), "GigabitEthernet0/0")
        rejected = self.service.save(
            {"host": "10.0.0.1", "interface_name": "Gi0/1", "interface_kind": "L3"}
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("discovery/profile", rejected["message"])

        existing = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0",
                "interface_kind": "L3",
                "ip_address": "192.0.2.1",
                "subnet_mask": "/24",
            }
        )
        self.assertTrue(existing["ok"], existing)
        self.assertEqual(existing["interface"]["subnet_mask"], "255.255.255.0")
        self.assertFalse(existing["interface"]["can_delete"])
        self.assertFalse(
            delete_router_interface(self.db, existing["interface"]["iface_id"])
        )

    def test_shutdown_only_sets_one_bit_and_renders_one_parameter(self) -> None:
        with closing(self.db._connect()) as connection:
            iface_id = int(
                connection.execute(
                    "SELECT iface_id FROM t02_interface_name WHERE interface_name = ?",
                    ("GigabitEthernet0/0",),
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE t02_interface_name SET ip_address = ?, subnet_mask = ?, "
                "description = NULL, shutdown = 0, action_Cfg = '0000000000000' "
                "WHERE iface_id = ?",
                ("192.168.25.2", "255.255.255.0", iface_id),
            )
            connection.execute(
                "INSERT INTO t02_router_iface_l3("
                "iface_id, mtu, speed, duplex, negotiation, proxy_arp, "
                "unreachables, directed_broadcast, sync_status, action_Cfg"
                ") VALUES (?, 1500, 'auto', 'auto', 1, 1, 1, 0, "
                "'synchronized', '00000')",
                (iface_id,),
            )
            connection.commit()

        result = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0",
                "interface_kind": "L3",
                "ip_address": "192.168.25.2",
                "subnet_mask": "255.255.255.0",
                "mtu": 1500,
                "speed": "auto",
                "duplex": "auto",
                "negotiation": True,
                "proxy_arp": True,
                "unreachables": True,
                "directed_broadcast": False,
                "shutdown": True,
            }
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["interface"]["action_Cfg"], "0000000000001")
        task = collect_interface_tasks(self.db, "10.0.0.1")[0]
        self.assertEqual(
            render_interface_commands(task),
            ["interface GigabitEthernet0/0", "shutdown", "exit"],
        )

        mark_interface_task_applied(self.db, task)
        stored = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0",
                "interface_kind": "L3",
                "ip_address": "192.168.25.2",
                "subnet_mask": "255.255.255.0",
                "mtu": 1500,
                "speed": "auto",
                "duplex": "auto",
                "negotiation": True,
                "proxy_arp": True,
                "unreachables": True,
                "directed_broadcast": False,
                "shutdown": True,
            }
        )
        self.assertEqual(stored["interface"]["action_Cfg"], "0000000000000")
        self.assertEqual(collect_interface_tasks(self.db, "10.0.0.1"), [])

    def test_loopback_is_virtual_and_omits_physical_line_commands(self) -> None:
        result = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Lo0",
                "interface_kind": "L3",
                "ip_address": "10.255.0.1",
                "subnet_mask": "/32",
            }
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["interface"]["interface_name"], "Loopback0")
        self.assertTrue(result["interface"]["can_delete"])

        task = next(
            task
            for task in collect_interface_tasks(self.db, "10.0.0.1")
            if task["interface"]["interface_name"] == "Loopback0"
        )
        commands = render_interface_commands(task)
        self.assertNotIn("speed auto", commands)
        self.assertNotIn("duplex auto", commands)
        self.assertNotIn("mtu 1500", commands)
        self.assertIn("ip address 10.255.0.1 255.255.255.255", commands)

    def test_unpushed_loopback_renumber_reuses_the_pending_row(self) -> None:
        created = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Loopback0",
                "interface_kind": "L3",
                "ip_address": "10.255.0.1",
                "subnet_mask": "/32",
            }
        )
        self.assertTrue(created["ok"], created)
        iface_id = created["interface"]["iface_id"]

        renamed = self.service.save(
            {
                "iface_id": iface_id,
                "host": "10.0.0.1",
                "interface_name": "Loopback1",
                "interface_kind": "L3",
                "ip_address": "10.255.0.1",
                "subnet_mask": "/32",
            }
        )

        self.assertTrue(renamed["ok"], renamed)
        self.assertEqual(renamed["interface"]["iface_id"], iface_id)
        with closing(self.db._connect()) as connection:
            rows = connection.execute(
                "SELECT iface_id, interface_name FROM t02_interface_name "
                "WHERE host = ? AND interface_name LIKE 'Loopback%'",
                ("10.0.0.1",),
            ).fetchall()
        self.assertEqual(
            [(row["iface_id"], row["interface_name"]) for row in rows],
            [(iface_id, "Loopback1")],
        )
        tasks = collect_interface_tasks(self.db, "10.0.0.1")
        loopbacks = [
            task for task in tasks
            if task["interface"]["interface_name"].startswith("Loopback")
        ]
        self.assertEqual(len(loopbacks), 1)
        commands = render_interface_commands(loopbacks[0])
        self.assertIn("interface Loopback1", commands)
        self.assertNotIn("interface Loopback0", commands)
        self.assertFalse(any(command.startswith("mtu ") for command in commands))

        with closing(self.db._connect()) as connection:
            connection.execute(
                "UPDATE t02_interface_name SET sync_status = 'synchronized' "
                "WHERE iface_id = ?",
                (iface_id,),
            )
            connection.commit()
        rejected = self.service.save(
            {
                "iface_id": iface_id,
                "host": "10.0.0.1",
                "interface_name": "Loopback2",
                "interface_kind": "L3",
                "ip_address": "10.255.0.1",
                "subnet_mask": "/32",
            }
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("unpushed", rejected["message"])

    def test_tunnel_and_subinterface_validate_and_render(self) -> None:
        invalid_tunnel = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Tunnel7",
                "interface_kind": "Tunnel",
                "tunnel_src": "Gi0/0",
                "tunnel_dst": "not-an-ip",
            }
        )
        self.assertFalse(invalid_tunnel["ok"])

        tunnel = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Tunnel7",
                "interface_kind": "Tunnel",
                "ip_address": "172.16.0.1",
                "subnet_mask": "/30",
                "tunnel_src": "Gi0/0",
                "tunnel_dst": "198.51.100.2",
            }
        )
        self.assertTrue(tunnel["ok"], tunnel)
        self.assertEqual(tunnel["interface"]["tunnel_src"], "GigabitEthernet0/0")

        subinterface = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0.100",
                "interface_kind": "Subinterface",
                "parent_interface": "Gi0/0",
                "vlan_id": 100,
                "native": True,
                "ip_address": "192.168.100.1",
                "subnet_mask": "/24",
            }
        )
        self.assertTrue(subinterface["ok"], subinterface)
        row = subinterface["interface"]
        self.assertEqual(row["parent_interface"], "GigabitEthernet0/0")
        self.assertEqual(row["interface_type"], "subinterface")

        task = next(
            task
            for task in collect_interface_tasks(self.db, "10.0.0.1")
            if task["interface"]["interface_name"] == "GigabitEthernet0/0.100"
        )
        self.assertIn("encapsulation dot1Q 100 native", render_interface_commands(task))

    def test_multiple_pending_subinterfaces_are_stored_as_distinct_rows(self) -> None:
        created = []
        for number in (100, 200):
            result = self.service.save(
                {
                    "iface_id": -1,
                    "host": "10.0.0.1",
                    "interface_name": f"Gi0/0.{number}",
                    "interface_kind": "Subinterface",
                    "parent_interface": "Gi0/0",
                    "vlan_id": number,
                    "ip_address": f"192.168.{number}.1",
                    "subnet_mask": "/24",
                }
            )
            self.assertTrue(result["ok"], result)
            created.append(result["interface"])

        self.assertNotEqual(created[0]["iface_id"], created[1]["iface_id"])
        with closing(self.db._connect()) as connection:
            rows = connection.execute(
                "SELECT i.iface_id, i.interface_name, s.vlan_id "
                "FROM t02_interface_name AS i "
                "JOIN t02_router_iface_subif AS s "
                "ON s.host = i.host AND s.subif_name = i.interface_name "
                "WHERE i.host = ? ORDER BY s.vlan_id",
                ("10.0.0.1",),
            ).fetchall()

        self.assertEqual(
            [(row["interface_name"], row["vlan_id"]) for row in rows],
            [
                ("GigabitEthernet0/0.100", 100),
                ("GigabitEthernet0/0.200", 200),
            ],
        )

    def test_subinterface_ignores_stale_physical_l3_pending_profile(self) -> None:
        result = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0.100",
                "interface_kind": "Subinterface",
                "parent_interface": "Gi0/0",
                "vlan_id": 100,
            }
        )
        self.assertTrue(result["ok"], result)
        iface_id = int(result["interface"]["iface_id"])
        with closing(self.db._connect()) as connection:
            connection.execute(
                "UPDATE t02_interface_name SET sync_status = 'synchronized' "
                "WHERE iface_id = ?;",
                (iface_id,),
            )
            connection.execute(
                "UPDATE t02_router_iface_subif SET sync_status = 'synchronized' "
                "WHERE host = ? AND subif_name = ?;",
                ("10.0.0.1", "GigabitEthernet0/0.100"),
            )
            connection.execute(
                "INSERT INTO t02_router_iface_l3(iface_id, sync_status) "
                "VALUES (?, 'pending_delete');",
                (iface_id,),
            )
            connection.commit()

        task = next(
            task
            for task in collect_interface_tasks(self.db, "10.0.0.1")
            if task["interface"]["interface_name"] == "GigabitEthernet0/0.100"
        )
        commands = render_interface_commands(task)

        self.assertEqual(commands, [])
        controller = InterfaceViewPushController(self.db, session_registry=object())
        self.assertFalse(controller.has_pending("10.0.0.1", "all"))
        self.assertEqual(controller.preview("10.0.0.1", "all")["commands"], "")

    def test_device_sync_classifies_and_persists_subinterface_profile(self) -> None:
        subinterface = parse_interface_block(
            "GigabitEthernet0/0.100",
            [
                "encapsulation dot1Q 100 native",
                "ip address 192.168.100.1 255.255.255.0",
                "no shutdown",
            ],
        )
        self.assertEqual(subinterface["interface_kind"], "Subinterface")
        self.assertEqual(subinterface["subif_vlan_id"], 100)
        self.assertEqual(subinterface["subif_native"], 1)

        with closing(self.db._connect()) as connection:
            # The parent may be absent from running-config while still being
            # implied by the observed subinterface.
            sync_interfaces(connection, "10.0.0.1", [subinterface])
            connection.commit()
            stored = connection.execute(
                "SELECT encapsulation, vlan_id, native, sync_status "
                "FROM t02_router_iface_subif WHERE host = ? AND subif_name = ?;",
                ("10.0.0.1", "GigabitEthernet0/0.100"),
            ).fetchone()
            subif_id = connection.execute(
                "SELECT iface_id FROM t02_interface_name "
                "WHERE host = ? AND interface_name = ?;",
                ("10.0.0.1", "GigabitEthernet0/0.100"),
            ).fetchone()[0]
            stale_l3_count = connection.execute(
                "SELECT COUNT(*) FROM t02_router_iface_l3 WHERE iface_id = ?;",
                (subif_id,),
            ).fetchone()[0]

        self.assertIsNotNone(stored)
        self.assertEqual(tuple(stored), ("dot1q", 100, 1, "synchronized"))
        self.assertEqual(stale_l3_count, 0)

    def test_brief_only_subinterface_never_creates_physical_l3_profile(self) -> None:
        subinterface = parse_interface_block("GigabitEthernet0/0.200", [])
        self.assertEqual(subinterface["interface_kind"], "Subinterface")

        with closing(self.db._connect()) as connection:
            sync_interfaces(connection, "10.0.0.1", [subinterface])
            connection.commit()
            iface_id = connection.execute(
                "SELECT iface_id FROM t02_interface_name "
                "WHERE host = ? AND interface_name = ?;",
                ("10.0.0.1", "GigabitEthernet0/0.200"),
            ).fetchone()[0]
            l3_count = connection.execute(
                "SELECT COUNT(*) FROM t02_router_iface_l3 WHERE iface_id = ?;",
                (iface_id,),
            ).fetchone()[0]

        self.assertEqual(l3_count, 0)

    def test_unpushed_virtual_delete_discards_draft_without_push_task(self) -> None:
        created = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/0.200",
                "interface_kind": "Subinterface",
                "parent_interface": "Gi0/0",
                "vlan_id": 200,
            }
        )
        self.assertTrue(created["ok"], created)
        self.assertTrue(
            delete_router_interface(self.db, created["interface"]["iface_id"])
        )
        self.assertFalse(
            any(
                task["interface"]["interface_name"] == "GigabitEthernet0/0.200"
                for task in collect_interface_tasks(self.db, "10.0.0.1")
            )
        )
        with closing(self.db._connect()) as connection:
            base_count = connection.execute(
                "SELECT COUNT(*) FROM t02_interface_name WHERE interface_name = ?",
                ("GigabitEthernet0/0.200",),
            ).fetchone()[0]
            profile_count = connection.execute(
                "SELECT COUNT(*) FROM t02_router_iface_subif WHERE subif_name = ?",
                ("GigabitEthernet0/0.200",),
            ).fetchone()[0]
        self.assertEqual((base_count, profile_count), (0, 0))

    def test_subinterface_parent_failure_rolls_back_base_row(self) -> None:
        result = self.service.save(
            {
                "host": "10.0.0.1",
                "interface_name": "Gi0/9.300",
                "interface_kind": "Subinterface",
                "parent_interface": "Gi0/9",
                "vlan_id": 300,
            }
        )
        self.assertFalse(result["ok"])
        with closing(self.db._connect()) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM t02_interface_name WHERE interface_name = ?",
                ("GigabitEthernet0/9.300",),
            ).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
