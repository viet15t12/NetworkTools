from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database.conversion import ConversionMixin
from features.fhrp.collector import collect_fhrp_tasks
from features.fhrp.commands import redact_fhrp_commands, render_fhrp_commands
from features.fhrp.service import FhrpService
from features.fhrp.schema import ensure_schema as ensure_fhrp_schema
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
            self.assertIn("no vrrp 20", render_fhrp_commands(tasks[0]))

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
            self.assertIn("no glbp 30", commands)

    def test_fhrp_delete_can_be_cancelled_without_losing_previous_states(self) -> None:
        service = FhrpService(self.db)
        candidates = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "hsrp",
            "group_number": 31,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "tracks": [{"track_object": "1", "decrement_value": 10}],
                }
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
            connection.execute(
                """
                UPDATE t08_fhrp_tracks
                SET sync_status = 'synchronized'
                WHERE member_id IN (
                    SELECT member_id FROM t08_fhrp_members
                    WHERE fhrp_id = ? AND host = '10.0.0.1'
                );
                """,
                (result["fhrp_id"],),
            )
            connection.commit()

        self.assertTrue(service.delete(result["fhrp_id"])["ok"])
        with self.db._connect() as connection:
            staged = connection.execute(
                """
                SELECT host, sync_status, delete_restore_status
                FROM t08_fhrp_members
                WHERE fhrp_id = ? ORDER BY host;
                """,
                (result["fhrp_id"],),
            ).fetchall()
        self.assertEqual(
            [tuple(row) for row in staged],
            [
                ("10.0.0.1", "pending_delete", "synchronized"),
                ("10.0.0.2", "pending_delete", "pending_apply"),
            ],
        )

        cancelled = service.cancel_delete(result["fhrp_id"])

        self.assertTrue(cancelled["ok"], cancelled)
        with self.db._connect() as connection:
            restored = connection.execute(
                """
                SELECT host, sync_status, delete_restore_status
                FROM t08_fhrp_members
                WHERE fhrp_id = ? ORDER BY host;
                """,
                (result["fhrp_id"],),
            ).fetchall()
            track_states = connection.execute(
                """
                SELECT m.host, t.sync_status, t.delete_restore_status
                FROM t08_fhrp_tracks AS t
                JOIN t08_fhrp_members AS m ON m.member_id = t.member_id
                WHERE m.fhrp_id = ? ORDER BY m.host;
                """,
                (result["fhrp_id"],),
            ).fetchall()
        expected = [
            ("10.0.0.1", "synchronized", None),
            ("10.0.0.2", "pending_apply", None),
        ]
        self.assertEqual([tuple(row) for row in restored], expected)
        self.assertEqual([tuple(row) for row in track_states], expected)
        self.assertEqual(collect_fhrp_tasks(self.db, "10.0.0.1"), [])
        self.assertEqual(
            collect_fhrp_tasks(self.db, "10.0.0.2")[0]["action"], "setup"
        )
        self.assertFalse(service.cancel_delete(result["fhrp_id"])["ok"])

    def test_gateway_cannot_equal_a_member_interface_address(self) -> None:
        result = FhrpService(self.db).matching_interfaces(
            ["10.0.0.1"], "192.168.10.2"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["interfaces"], [])

    def test_fhrp_matches_synchronized_switch_svi_without_router_table_mirroring(self) -> None:
        with self.db._connect() as connection:
            connection.execute(
                """
                INSERT INTO t01_devices(
                    host, device_name, method, os, role, device_type, connection_status
                ) VALUES ('10.0.0.3', 'SW3', 'SSH', 'cisco', 'sw3', 'sw3', 'connected')
                """
            )
            connection.execute(
                "INSERT INTO t06_vlan_db(host, vlan_id, vlan_name, success, device_present) "
                "VALUES ('10.0.0.3', 10, 'Users', 'synchronized', 1)"
            )
            connection.execute(
                """
                INSERT INTO t06_svi_interface(
                    host, vlan_id, ip_address, subnet_mask,
                    shutdown, sync_status, device_present
                ) VALUES (
                    '10.0.0.3', 10, '192.168.10.4', '255.255.255.0',
                    0, 'synchronized', 1
                )
                """
            )
            connection.commit()

        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.3"], "192.168.10.1"
        )["interfaces"]
        self.assertEqual(
            {(row["host"], row["interface_kind"]) for row in interfaces},
            {("10.0.0.1", "router"), ("10.0.0.3", "svi")},
        )
        result = service.save({
            "protocol": "hsrp",
            "group_number": 40,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "interface_kind": row["interface_kind"],
                }
                for row in interfaces
            ],
        })
        self.assertTrue(result["ok"], result)
        svi_task = collect_fhrp_tasks(self.db, "10.0.0.3")[0]
        self.assertEqual(svi_task["config"]["interface_name"], "Vlan10")
        self.assertIn("interface Vlan10", render_fhrp_commands(svi_task))

    def test_fhrp_excludes_interfaces_that_are_still_waiting_for_push(self) -> None:
        with self.db._connect() as connection:
            connection.execute(
                "UPDATE t02_interface_name SET sync_status = 'pending_apply' "
                "WHERE host = '10.0.0.1'"
            )
            connection.commit()

        interfaces = FhrpService(self.db).matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        self.assertEqual([row["host"] for row in interfaces], ["10.0.0.2"])

    def test_fhrp_rejects_mismatched_authentication_between_members(self) -> None:
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        members = [
            {
                "host": row["host"],
                "iface_id": row["iface_id"],
                "interface_kind": row["interface_kind"],
                "auth_type": "plain" if index == 0 else "none",
                "auth_secret": "shared" if index == 0 else "",
            }
            for index, row in enumerate(interfaces)
        ]

        result = service.save({
            "protocol": "hsrp",
            "group_number": 41,
            "default_gateway": "192.168.10.1",
            "members": members,
        })

        self.assertFalse(result["ok"])
        self.assertIn("same version, timers, authentication", result["message"])

    def test_fhrp_rejects_second_primary_vip_for_same_interface_group(self) -> None:
        service = FhrpService(self.db)

        def payload(gateway: str) -> dict[str, object]:
            interfaces = service.matching_interfaces(
                ["10.0.0.1", "10.0.0.2"], gateway
            )["interfaces"]
            return {
                "protocol": "hsrp",
                "group_number": 42,
                "default_gateway": gateway,
                "members": [
                    {
                        "host": row["host"],
                        "iface_id": row["iface_id"],
                        "interface_kind": row["interface_kind"],
                    }
                    for row in interfaces
                ],
            }

        self.assertTrue(service.save(payload("192.168.10.1"))["ok"])
        conflict = service.save(payload("192.168.10.254"))
        self.assertFalse(conflict["ok"])
        self.assertIn("already exists", conflict["message"])

    def test_vrrp_uses_version_two_and_rejects_reserved_owner_priority(self) -> None:
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        members = [
            {
                "host": row["host"],
                "iface_id": row["iface_id"],
                "interface_kind": row["interface_kind"],
            }
            for row in interfaces
        ]
        result = service.save({
            "protocol": "vrrp",
            "group_number": 43,
            "default_gateway": "192.168.10.1",
            "members": members,
        })
        self.assertTrue(result["ok"], result)
        with self.db._connect() as connection:
            versions = {
                row[0]
                for row in connection.execute("SELECT version FROM t08_vrrp_options")
            }
        self.assertEqual(versions, {2})

        members[0]["priority"] = 255
        owner = service.save({
            "protocol": "vrrp",
            "group_number": 44,
            "default_gateway": "192.168.10.254",
            "members": members,
        })
        self.assertFalse(owner["ok"])
        self.assertIn("address-owner", owner["message"])

        for member in members:
            member["priority"] = 100
            member["version"] = 3
        version_three = service.save({
            "protocol": "vrrp",
            "group_number": 44,
            "default_gateway": "192.168.10.254",
            "members": members,
        })
        self.assertFalse(version_three["ok"])
        self.assertIn("supports VRRPv2 only", version_three["message"])

    def test_fhrp_rejects_member_interfaces_with_different_masks(self) -> None:
        with self.db._connect() as connection:
            connection.execute(
                "UPDATE t02_interface_name SET subnet_mask = '255.255.255.128' "
                "WHERE host = '10.0.0.2'"
            )
            connection.commit()
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "hsrp",
            "group_number": 46,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "interface_kind": row["interface_kind"],
                }
                for row in interfaces
            ],
        })
        self.assertFalse(result["ok"])
        self.assertIn("same IPv4 subnet and prefix", result["message"])

    def test_glbp_renderer_applies_saved_weighting_and_forwarder_policy(self) -> None:
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "glbp",
            "group_number": 47,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "interface_kind": row["interface_kind"],
                    "hello_ms": 1000,
                    "hold_ms": 3000,
                    "weighting_max": 120,
                    "weighting_lower": 80,
                    "weighting_upper": 110,
                    "forwarder_preempt": True,
                    "forwarder_preempt_delay_sec": 10,
                    "shutdown": True,
                }
                for row in interfaces
            ],
        })
        self.assertTrue(result["ok"], result)
        commands = render_fhrp_commands(
            collect_fhrp_tasks(self.db, "10.0.0.1")[0]
        )
        self.assertIn("glbp 47 timers 1 3", commands)
        self.assertIn("glbp 47 weighting 120 lower 80 upper 110", commands)
        self.assertIn("glbp 47 forwarder preempt delay minimum 10", commands)
        self.assertIn("glbp 47 shutdown", commands)

    def test_fhrp_remove_cleans_group_policy_not_only_virtual_ip(self) -> None:
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        result = service.save({
            "protocol": "hsrp",
            "group_number": 45,
            "default_gateway": "192.168.10.1",
            "members": [
                {
                    "host": row["host"],
                    "iface_id": row["iface_id"],
                    "interface_kind": row["interface_kind"],
                    "preempt": True,
                    "auth_type": "md5-key",
                    "auth_secret": "shared-key",
                    "hello_ms": 1000,
                    "hold_ms": 3000,
                    "tracks": [{"track_object": "1", "decrement_value": 20}],
                }
                for row in interfaces
            ],
        })
        self.assertTrue(result["ok"], result)
        self.assertTrue(service.delete(result["fhrp_id"])["ok"])
        commands = render_fhrp_commands(
            collect_fhrp_tasks(self.db, "10.0.0.1")[0]
        )
        for command in (
            "no standby 45 ip 192.168.10.1",
            "no standby 45 track 1",
            "no standby 45 authentication",
            "no standby 45 timers",
            "no standby 45 priority",
            "no standby 45 preempt",
            "no standby 45",
        ):
            self.assertIn(command, commands)

    def test_fhrp_worker_verifies_device_state_and_redacts_echoed_secret(self) -> None:
        class Connection:
            def __init__(self):
                self.config_calls = 0
                self.show_calls = 0

            def send_config_set(self, _commands, **_kwargs):
                self.config_calls += 1
                return "standby 50 authentication shared-key"

            def send_command(self, command, **_kwargs):
                self.show_calls += 1
                if command.startswith("show running-config interface"):
                    return "interface GigabitEthernet0/0\n standby 50 ip 192.168.10.1"
                return "Gi0/0 50 Active 192.168.10.1"

        task = {
            "target": {"ip": "10.0.0.1"},
            "sub_type": "hsrp",
            "action": "setup",
            "config": {
                "member_id": 1,
                "fhrp_id": 1,
                "protocol": "hsrp",
                "interface_name": "GigabitEthernet0/0",
                "group_number": 50,
                "virtual_ip": "192.168.10.1",
                "priority": 100,
                "preempt": 1,
                "shutdown": 0,
                "options": {
                    "version": 2,
                    "hello_ms": 3000,
                    "hold_ms": 10000,
                    "preempt_delay_min_sec": 0,
                    "preempt_delay_reload_sec": 0,
                    "auth_type": "md5-key",
                    "auth_secret": "shared-key",
                },
                "tracks": [],
            },
        }
        connector = type("Connector", (), {"connection": Connection()})()

        report = push_fhrp_tasks([task], "cisco_ios", lambda _host: connector)[0]

        self.assertEqual(report["status"], "SUCCESS")
        self.assertNotIn("shared-key", report["log"])
        self.assertIn("<redacted>", report["log"])
        self.assertIn("operational state verified", report["log"])

        shows_before_apply_only = connector.connection.show_calls
        fast_reports = push_fhrp_tasks(
            [task, task],
            "cisco_ios",
            lambda _host: connector,
            verify=False,
        )

        self.assertTrue(all(item["status"] == "SUCCESS" for item in fast_reports))
        self.assertEqual(connector.connection.config_calls, 2)
        self.assertEqual(connector.connection.show_calls, shows_before_apply_only)

    def test_fhrp_worker_does_not_sync_when_operational_group_is_missing(self) -> None:
        class Connection:
            def send_config_set(self, _commands, **_kwargs):
                return "configuration accepted"

            def send_command(self, command, **_kwargs):
                if command.startswith("show running-config interface"):
                    return "interface GigabitEthernet0/0\n vrrp 51 ip 192.168.10.1"
                return ""

        task = {
            "target": {"ip": "10.0.0.1"},
            "sub_type": "vrrp",
            "action": "setup",
            "config": {
                "member_id": 1,
                "fhrp_id": 1,
                "protocol": "vrrp",
                "interface_name": "GigabitEthernet0/0",
                "group_number": 51,
                "virtual_ip": "192.168.10.1",
                "priority": 100,
                "preempt": 1,
                "shutdown": 0,
                "options": {
                    "version": 2,
                    "advertisement_ms": 1000,
                    "accept_mode": 0,
                    "auth_type": "none",
                    "auth_secret": None,
                },
                "tracks": [],
            },
        }
        connector = type("Connector", (), {"connection": Connection()})()

        report = push_fhrp_tasks([task], "cisco_ios", lambda _host: connector)[0]

        self.assertEqual(report["status"], "FAILED")
        self.assertIn("operational verification", report["log"])

    def test_deferred_fhrp_verification_advances_the_captured_member(self) -> None:
        service = FhrpService(self.db)
        interfaces = service.matching_interfaces(
            ["10.0.0.1", "10.0.0.2"], "192.168.10.1"
        )["interfaces"]
        saved = service.save(
            {
                "protocol": "hsrp",
                "group_number": 52,
                "default_gateway": "192.168.10.1",
                "members": [
                    {"host": row["host"], "iface_id": row["iface_id"]}
                    for row in interfaces
                ],
            }
        )
        self.assertTrue(saved["ok"], saved)
        controller = FhrpViewPushController(self.db)
        task = controller.collect_pending_tasks("10.0.0.1", "hsrp")[0]
        context = controller.post_push_context([task], {"ok": True})

        class Connection:
            def send_command(self, command, **_kwargs):
                if command.startswith("show running-config interface"):
                    return (
                        "interface GigabitEthernet0/0\n"
                        " standby 52 ip 192.168.10.1"
                    )
                return "Gi0/0 52 Active 192.168.10.1"

        verified = controller.verify_after_push(
            "10.0.0.1",
            "hsrp",
            type("Connector", (), {"connection": Connection()})(),
            context,
        )

        self.assertTrue(verified["ok"], verified)
        with self.db._connect() as connection:
            state = connection.execute(
                "SELECT sync_status FROM t08_fhrp_members WHERE host = '10.0.0.1';"
            ).fetchone()[0]
        self.assertEqual(state, "synchronized")

    def test_legacy_fhrp_schema_upgrade_preserves_member_and_aligns_vrrp(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE t01_devices(host TEXT PRIMARY KEY);
            CREATE TABLE t02_interface_name(
                iface_id INTEGER PRIMARY KEY, host TEXT NOT NULL,
                FOREIGN KEY(host) REFERENCES t01_devices(host)
            );
            CREATE TABLE t06_svi_interface(id INTEGER PRIMARY KEY, host TEXT NOT NULL);
            CREATE TABLE t08_fhrp_groups(fhrp_id INTEGER PRIMARY KEY);
            CREATE TABLE t08_fhrp_members(
                member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fhrp_id INTEGER NOT NULL, host TEXT NOT NULL, iface_id INTEGER NOT NULL,
                priority INTEGER NOT NULL DEFAULT 100, preempt INTEGER NOT NULL DEFAULT 0,
                shutdown INTEGER NOT NULL DEFAULT 0,
                sync_status TEXT NOT NULL DEFAULT 'pending_apply',
                FOREIGN KEY(fhrp_id) REFERENCES t08_fhrp_groups(fhrp_id),
                FOREIGN KEY(host) REFERENCES t01_devices(host),
                FOREIGN KEY(iface_id) REFERENCES t02_interface_name(iface_id)
            );
            CREATE TABLE t08_vrrp_options(
                member_id INTEGER PRIMARY KEY, version INTEGER NOT NULL,
                FOREIGN KEY(member_id) REFERENCES t08_fhrp_members(member_id)
            );
            CREATE TRIGGER trg_t08_group_protocol_immutable
            BEFORE UPDATE ON t08_fhrp_groups
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1 FROM t08_fhrp_members WHERE fhrp_id = OLD.fhrp_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'group is populated');
            END;
            INSERT INTO t01_devices VALUES ('r1');
            INSERT INTO t02_interface_name VALUES (7, 'r1');
            INSERT INTO t08_fhrp_groups VALUES (3);
            INSERT INTO t08_fhrp_members(
                member_id, fhrp_id, host, iface_id
            ) VALUES (5, 3, 'r1', 7);
            INSERT INTO t08_vrrp_options VALUES (5, 3);
            """
        )

        changes = ensure_fhrp_schema(connection)

        member = connection.execute(
            "SELECT member_id, interface_kind FROM t08_fhrp_members"
        ).fetchone()
        self.assertEqual(member, (5, "router"))
        self.assertEqual(
            connection.execute("SELECT version FROM t08_vrrp_options").fetchone()[0],
            2,
        )
        self.assertIn("t08_fhrp_members.interface_kind", changes)
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        connection.close()


if __name__ == "__main__":
    unittest.main()
