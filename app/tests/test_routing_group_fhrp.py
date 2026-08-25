from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database.conversion import ConversionMixin
from features.fhrp.collector import collect_fhrp_tasks
from features.fhrp.commands import redact_fhrp_commands, render_fhrp_commands
from features.fhrp.service import FhrpService
from features.fhrp.view_push import FhrpViewPushController
from features.fhrp.worker import push_fhrp_tasks
from features.routing.group_service import RoutingGroupService
from infrastructure.database.paths import DEVICE_NETWORK_SCHEMA_DIR
from scripts.build_databases import build_database


class _ClosingConnection(sqlite3.Connection):
    """Match DatabaseManager's close-on-transaction-exit connection."""

    def __exit__(self, exc_type, exc, traceback):
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


class _Db(ConversionMixin):
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection


class RoutingGroupAndFhrpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        build_database(DEVICE_NETWORK_SCHEMA_DIR, self.db_path)
        self.db = _Db(self.db_path)
        with self.db._connect() as connection:
            for index, host in enumerate(("10.0.0.1", "10.0.0.2"), start=1):
                connection.execute(
                    """
                    INSERT INTO t01_devices (
                        host, device_name, method, os, role,
                        device_type, connection_status
                    ) VALUES (?, ?, 'SSH', 'cisco', 'rou', 'router', 'connected');
                    """,
                    (host, f"R{index}"),
                )
                connection.execute(
                    """
                    INSERT INTO t02_interface_name (
                        host, interface_name, ip_address, subnet_mask, sync_status
                    ) VALUES (?, 'GigabitEthernet0/0', ?, '255.255.255.0', 'synchronized');
                    """,
                    (host, f"192.168.10.{index + 1}"),
                )
            connection.commit()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_routing_group_filters_and_saves_host_owned_networks(self) -> None:
        service = RoutingGroupService(self.db)
        hosts = service.options()["hosts"]
        self.assertEqual([row["host"] for row in hosts], ["10.0.0.1", "10.0.0.2"])
        targets = []
        for index, host in enumerate(hosts, start=1):
            network = host["networks"][0]
            targets.append(
                {
                    "host": host["host"],
                    "process_id": index,
                    "router_id": f"1.1.1.{index}",
                    "networks": [
                        {
                            "network": network["network"],
                            "wildcard": network["wildcard"],
                            "area": 0,
                        }
                    ],
                }
            )

        result = service.save(
            "ospf",
            targets,
            {"reference_bandwidth": 1000, "authentication_cfg": True},
        )

        self.assertTrue(result["ok"], result)
        with self.db._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM t04_ospf_processes").fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t04_ospf_areas WHERE authentication = 'message-digest'"
                ).fetchone()[0],
                2,
            )

    def test_routing_group_rejects_more_than_five_hosts(self) -> None:
        result = RoutingGroupService(self.db).save(
            "ospf",
            [
                {"host": f"10.0.0.{index}", "process_id": index, "networks": []}
                for index in range(1, 7)
            ],
            {},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Routing Group supports at most 5 hosts")

    def test_routing_group_partial_result_names_each_failed_host_and_reason(self) -> None:
        with self.db._connect() as connection:
            connection.execute(
                """
                INSERT INTO t04_ospf_processes (
                    host, process_id, router_id, sync_status
                ) VALUES ('10.0.0.1', 1, '1.1.1.1', 'synchronized');
                """
            )
            connection.commit()

        result = RoutingGroupService(self.db).save(
            "ospf",
            [
                {
                    "host": "10.0.0.1",
                    "process_id": 1,
                    "networks": [
                        {
                            "network": "192.168.10.0",
                            "wildcard": "0.0.0.255",
                            "area": 0,
                        }
                    ],
                },
                {
                    "host": "10.0.0.2",
                    "process_id": 1,
                    "networks": [
                        {
                            "network": "192.168.10.0",
                            "wildcard": "0.0.0.255",
                            "area": 0,
                        }
                    ],
                },
            ],
            {},
        )

        self.assertTrue(result["partial"])
        self.assertEqual(result["successful"], ["10.0.0.2"])
        self.assertIn("10.0.0.1: process_id 1 already exists", result["message"])
        self.assertNotIn("closed database", result["message"])

    def test_routing_group_retry_reuses_a_locally_pending_ospf_process(self) -> None:
        with self.db._connect() as connection:
            connection.execute(
                """
                INSERT INTO t04_ospf_processes (
                    host, process_id, router_id, sync_status
                ) VALUES ('10.0.0.1', 1, '1.1.1.1', 'pending_apply');
                """
            )
            connection.commit()

        targets = [
            {
                "host": host,
                "process_id": 1,
                "router_id": router_id,
                "networks": [
                    {
                        "network": "192.168.10.0",
                        "wildcard": "0.0.0.255",
                        "area": 0,
                    }
                ],
            }
            for host, router_id in (
                ("10.0.0.1", "1.1.1.1"),
                ("10.0.0.2", "2.2.2.2"),
            )
        ]

        result = RoutingGroupService(self.db).save("ospf", targets, {})

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["successful"], ["10.0.0.1", "10.0.0.2"])

    def test_routing_group_retry_reuses_locally_pending_eigrp_processes(self) -> None:
        targets = [
            {
                "host": host,
                "as_number": 100,
                "router_id": router_id,
                "networks": [
                    {
                        "network": "192.168.10.0",
                        "wildcard": "0.0.0.255",
                    }
                ],
            }
            for host, router_id in (
                ("10.0.0.1", "1.1.1.1"),
                ("10.0.0.2", "2.2.2.2"),
            )
        ]
        service = RoutingGroupService(self.db)

        first = service.save("eigrp", targets, {"maximum_paths": 2})
        retried = service.save("eigrp", targets, {"maximum_paths": 4})

        self.assertTrue(first["ok"], first)
        self.assertTrue(retried["ok"], retried)
        with self.db._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t04_eigrp_processes"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t04_eigrp_networks"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                {
                    row[0]
                    for row in connection.execute(
                        "SELECT maximum_paths FROM t04_eigrp_processes"
                    ).fetchall()
                },
                {4},
            )

    def test_fhrp_filters_interface_and_builds_multi_host_hsrp(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )
        self.assertTrue(candidates["ok"])
        self.assertEqual(len(candidates["interfaces"]), 2)
        members = [
            {
                "host": row["host"],
                "iface_id": row["iface_id"],
                "priority": 110 - index,
                "preempt": True,
                "auth_type": "md5-key",
                "auth_secret": "private-key",
            }
            for index, row in enumerate(candidates["interfaces"])
        ]

        result = service.save(
            {
                "protocol": "hsrp",
                "group_number": 10,
                "default_gateway": "192.168.10.1",
                "members": members,
            }
        )

        self.assertTrue(result["ok"], result)
        tasks = collect_fhrp_tasks(self.db, "10.0.0.1")
        self.assertEqual(len(tasks), 1)
        commands = render_fhrp_commands(tasks[0])
        self.assertIn("standby 10 ip 192.168.10.1", commands)
        self.assertFalse(
            any(command.startswith("standby 10 timers") for command in commands)
        )
        preview = "\n".join(redact_fhrp_commands(commands))
        self.assertNotIn("private-key", preview)
        self.assertIn("<redacted>", preview)

        deleted = service.delete(result["fhrp_id"])
        self.assertTrue(deleted["ok"], deleted)
        for host in ("10.0.0.1", "10.0.0.2"):
            delete_tasks = collect_fhrp_tasks(self.db, host)
            self.assertEqual(len(delete_tasks), 1)
            self.assertEqual(delete_tasks[0]["action"], "remove")
            self.assertIn(
                "no standby 10 ip 192.168.10.1",
                render_fhrp_commands(delete_tasks[0]),
            )
        with self.db._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t08_fhrp_groups WHERE fhrp_id = ?",
                    (result["fhrp_id"],),
                ).fetchone()[0],
                1,
            )

    def test_fhrp_retry_replaces_only_the_local_pending_draft(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        payload = {
            "protocol": "hsrp",
            "group_number": 11,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "priority": 100,
                    "preempt": True,
                }
                for row in candidates
            ],
        }

        first = service.save(payload)
        payload["members"][0]["priority"] = 120
        retried = service.save(payload)

        self.assertTrue(first["ok"], first)
        self.assertTrue(retried["ok"], retried)
        with self.db._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t08_fhrp_groups"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM t08_fhrp_members"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT priority FROM t08_fhrp_members "
                    "WHERE host = '10.0.0.1'"
                ).fetchone()[0],
                120,
            )

    def test_fhrp_rejects_protocol_mixing_for_the_same_gateway_and_host(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        members = [
            {"host": row["host"], "iface_id": row["iface_id"], "preempt": True}
            for row in candidates
        ]

        first = service.save(
            {
                "protocol": "hsrp",
                "group_number": 1,
                "default_gateway": "192.168.10.1",
                "members": members,
            }
        )
        mixed = service.save(
            {
                "protocol": "glbp",
                "group_number": 2,
                "default_gateway": "192.168.10.1",
                "members": members,
            }
        )

        self.assertTrue(first["ok"], first)
        self.assertFalse(mixed["ok"])
        self.assertIn("already managed by HSRP group 1", mixed["message"])

    def test_fhrp_view_push_filters_tasks_by_selected_protocol(self) -> None:
        service = FhrpService(self.db)
        for protocol, group_number, gateway in (
            ("hsrp", 1, "192.168.10.1"),
            ("glbp", 2, "192.168.10.254"),
        ):
            candidates = service.matching_interfaces(
                ["10.0.0.1", "10.0.0.2"], gateway
            )["interfaces"]
            result = service.save(
                {
                    "protocol": protocol,
                    "group_number": group_number,
                    "default_gateway": gateway,
                    "members": [
                        {"host": row["host"], "iface_id": row["iface_id"]}
                        for row in candidates
                    ],
                }
            )
            self.assertTrue(result["ok"], result)

        controller = FhrpViewPushController(self.db)
        hsrp_tasks = controller.collect_pending_tasks("10.0.0.1", "hsrp")
        glbp_tasks = controller.collect_pending_tasks("10.0.0.1", "glbp")

        self.assertEqual([task["sub_type"] for task in hsrp_tasks], ["hsrp"])
        self.assertEqual([task["sub_type"] for task in glbp_tasks], ["glbp"])

    def test_fhrp_rejects_more_than_five_hosts(self) -> None:
        result = FhrpService(self.db).save(
            {
                "protocol": "hsrp",
                "group_number": 12,
                "default_gateway": "192.168.10.1",
                "members": [
                    {"host": f"10.0.0.{index}", "iface_id": index}
                    for index in range(1, 7)
                ],
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("at most 5", result["message"])

    def test_fhrp_cli_rejection_is_not_reported_as_success(self) -> None:
        class Connection:
            def send_config_set(self, _commands, **_kwargs):
                return "% Invalid input detected at '^' marker."

        connector = type("Connector", (), {"connection": Connection()})()
        task = {
            "target": {"ip": "10.0.0.1"},
            "sub_type": "hsrp",
            "action": "setup",
            "config": {
                "member_id": 1,
                "fhrp_id": 1,
                "protocol": "hsrp",
                "interface_name": "GigabitEthernet0/0",
                "group_number": 10,
                "virtual_ip": "192.168.10.1",
                "priority": 100,
                "preempt": 1,
                "shutdown": 0,
                "options": {
                    "version": 2,
                    "hello_ms": 3000,
                    "hold_ms": 10000,
                    "preempt_delay_min_sec": 0,
                    "auth_type": "none",
                    "auth_secret": None,
                },
                "tracks": [],
            },
        }

        report = push_fhrp_tasks(
            [task], "cisco_ios", lambda _host: connector
        )

        self.assertEqual(report[0]["status"], "FAILED")
        self.assertIn("Invalid input", report[0]["log"])

    def test_fhrp_delete_preserves_remove_push_for_synchronized_members(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "vrrp",
            "group_number": 20,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "priority": 100,
                    "preempt": True,
                }
                for row in candidates
            ],
        })
        self.assertTrue(result["ok"], result)
        with self.db._connect() as connection:
            connection.execute(
                "UPDATE t08_fhrp_members SET sync_status = 'synchronized' "
                "WHERE fhrp_id = ?",
                (result["fhrp_id"],),
            )
            connection.commit()

        deleted = service.delete(result["fhrp_id"])

        self.assertTrue(deleted["ok"], deleted)
        for host in ("10.0.0.1", "10.0.0.2"):
            tasks = collect_fhrp_tasks(self.db, host)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["action"], "remove")
            self.assertIn(
                "no vrrp 20 ip 192.168.10.1",
                render_fhrp_commands(tasks[0]),
            )
            self.assertIn("no vrrp 20 preempt", render_fhrp_commands(tasks[0]))

    def test_fhrp_delete_handles_partially_pushed_multi_host_group(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "glbp",
            "group_number": 30,
            "default_gateway": "192.168.10.1",
            "members": [
                {"host": row["host"], "iface_id": row["iface_id"]}
                for row in candidates
            ],
        })
        self.assertTrue(result["ok"], result)
        with self.db._connect() as connection:
            connection.execute(
                "UPDATE t08_fhrp_members SET sync_status = 'synchronized' "
                "WHERE fhrp_id = ? AND host = '10.0.0.1'",
                (result["fhrp_id"],),
            )
            connection.commit()

        self.assertTrue(service.delete(result["fhrp_id"])["ok"])

        for host in ("10.0.0.1", "10.0.0.2"):
            pushed_tasks = collect_fhrp_tasks(self.db, host)
            self.assertEqual(len(pushed_tasks), 1)
            self.assertEqual(pushed_tasks[0]["action"], "remove")
            commands = render_fhrp_commands(pushed_tasks[0])
            self.assertIn("no glbp 30 preempt", commands)
            self.assertIn("no glbp 30 ip 192.168.10.1", commands)

    def test_gateway_cannot_equal_a_member_interface_address(self) -> None:
        result = FhrpService(self.db).matching_interfaces(
            ["10.0.0.1"], "192.168.10.2"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["interfaces"], [])


if __name__ == "__main__":
    unittest.main()
