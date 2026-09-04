"""Regression tests for the app-native router-interface push pipeline."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from core.database.view_push_slots import ViewPushSlotsMixin
from features.interfaces.view_push import InterfaceViewPushController


APP_DIR = Path(__file__).resolve().parents[1]


class _Connection:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.output = "configuration accepted"

    def send_config_set(self, commands, **_kwargs):
        self.commands.extend(commands)
        return self.output


class _Connector:
    def __init__(self) -> None:
        self.connection = _Connection()


class _FailingSessionRegistry:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def get_connector(self, _host: str):
        return None

    def open(self, host: str) -> dict[str, object]:
        self.opened.append(host)
        return {
            "ok": False,
            "severity": "error",
            "message": f"Open session failed for {host}: CONNECTION_TIMEOUT.",
        }


class _ManagedSessionRegistry:
    def __init__(self, connector: object) -> None:
        self.connector = connector
        self.execute_calls = 0
        self.in_operation = False

    def execute(self, _host: str, operation, *, ensure_open=True):
        self.execute_calls += 1
        self.in_operation = True
        try:
            return {"ok": True, "value": operation(self.connector)}
        finally:
            self.in_operation = False

    def get_connector(self, _host: str):
        if not self.in_operation:
            raise AssertionError("connector used outside the per-host operation lock")
        return self.connector


class _Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.reconciliations: list[tuple[str, object]] = []

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

    def reconcileViewPushSnapshot(self, host: str, connector: object):
        self.reconciliations.append((host, connector))
        return {"ok": True, "message": "Running-config synchronized."}


class _Controller(InterfaceViewPushController):
    def __init__(self, db: _Database, connector: _Connector) -> None:
        super().__init__(db)
        self.connector = connector

    def _session_provider_for_host(self, _host: str):
        return lambda _target: self.connector


class InterfaceViewPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        schemas = (
            APP_DIR
            / "infrastructure"
            / "database"
            / "schemas"
            / "device_network"
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            for name in ("01_core_devices.sql", "02_interface_router_l3.sql"):
                connection.executescript(
                    (schemas / name).read_text(encoding="utf-8")
                )
            connection.execute(
                """
                INSERT INTO t01_devices(host, os, method, device_type)
                VALUES ('10.0.0.1', 'cisco', 'SSH', 'router');
                """
            )
            iface_id = connection.execute(
                """
                INSERT INTO t02_interface_name(
                    host, interface_name, ip_address, subnet_mask,
                    description, shutdown, sync_status
                ) VALUES (
                    '10.0.0.1', 'GigabitEthernet0/0',
                    '192.0.2.1', '255.255.255.0', 'WAN uplink', 0, 'pending_apply'
                );
                """
            ).lastrowid
            connection.execute(
                """
                INSERT INTO t02_router_iface_l3(
                    iface_id, secondary_ip, secondary_mask, mtu, bandwidth,
                    speed, duplex, negotiation, proxy_arp, unreachables,
                    directed_broadcast, sync_status, action_Cfg
                ) VALUES (
                    ?, '198.51.100.1', '255.255.255.0', 1600, 100000,
                    '1000', 'full', 0, 0, 1, 1, 'pending_apply', '11111'
                );
                """,
                (iface_id,),
            )
            connection.commit()
        self.db = _Database(self.db_path)
        self.connector = _Connector()
        self.controller = _Controller(self.db, self.connector)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _states(self) -> tuple[str, str]:
        with closing(self.db._connect()) as connection:
            base = str(connection.execute(
                "SELECT sync_status FROM t02_interface_name;"
            ).fetchone()[0])
            profile = str(connection.execute(
                "SELECT sync_status FROM t02_router_iface_l3;"
            ).fetchone()[0])
        return base, profile

    def test_preview_renders_full_l3_profile_without_transport(self) -> None:
        preview = self.controller.preview("10.0.0.1", "all")
        self.assertTrue(preview["ok"], preview)
        self.assertIn("interface GigabitEthernet0/0", preview["commands"])
        self.assertIn("ip address 192.0.2.1 255.255.255.0", preview["commands"])
        self.assertIn(
            "ip address 198.51.100.1 255.255.255.0 secondary",
            preview["commands"],
        )
        self.assertIn("mtu 1600", preview["commands"])
        self.assertIn("speed 1000", preview["commands"])
        self.assertIn("no negotiation auto", preview["commands"])
        self.assertEqual(self.connector.connection.commands, [])

    def test_successful_push_marks_base_and_profile_applied(self) -> None:
        result = self.controller.push("10.0.0.1", "all")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self._states(), ("synchronized", "synchronized"))
        self.assertFalse(self.controller.has_pending("10.0.0.1", "all"))
        self.assertEqual(
            self.db.reconciliations,
            [("10.0.0.1", self.connector)],
        )
        self.assertTrue(result["reconciliation"]["ok"])

    def test_default_auto_negotiation_is_not_emitted_for_ios_compatibility(self) -> None:
        with closing(self.db._connect()) as connection:
            connection.execute(
                "UPDATE t02_router_iface_l3 SET negotiation = 1;"
            )
            connection.commit()

        preview = self.controller.preview("10.0.0.1", "all")

        self.assertTrue(preview["ok"], preview)
        self.assertNotIn("negotiation auto", preview["commands"])

    def test_post_push_reconciliation_collects_backs_up_and_force_syncs(self) -> None:
        calls: list[tuple] = []
        connector = SimpleNamespace(
            collect_running_config=lambda: {
                "ok": True,
                "running_config": "interface GigabitEthernet0/1\n ip address 192.168.12.10 255.255.255.0\n",
                "interface_brief": "GigabitEthernet0/1 192.168.12.10 YES manual up up",
            }
        )
        backup_service = SimpleNamespace(
            save_snapshot=lambda host, config: (
                calls.append(("backup", host, config))
                or {"ok": True, "changed": True, "commitId": "abc"}
            )
        )
        sync_service = SimpleNamespace(
            sync_manual_snapshot=lambda *args, **kwargs: (
                calls.append(("sync", args, kwargs))
                or {"ok": True, "message": "Manual Sync completed."}
            )
        )
        owner = SimpleNamespace(
            _config_backup_service=backup_service,
            _config_sync_service=sync_service,
        )

        result = ViewPushSlotsMixin.reconcileViewPushSnapshot(
            owner, "10.0.0.1", connector
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(calls[0][0:2], ("backup", "10.0.0.1"))
        self.assertEqual(calls[1][0], "sync")
        self.assertEqual(calls[1][2]["mode"], "force_device_state")

    def test_device_error_keeps_database_pending(self) -> None:
        self.connector.connection.output = "% Invalid input detected"
        result = self.controller.push("10.0.0.1", "all")
        self.assertFalse(result["ok"])
        self.assertEqual(self._states(), ("pending_apply", "pending_apply"))

    def test_push_uses_injected_registry_and_keeps_session_error_detail(self) -> None:
        registry = _FailingSessionRegistry()
        controller = InterfaceViewPushController(self.db, registry)

        result = controller.push("10.0.0.1", "all")

        self.assertFalse(result["ok"])
        self.assertEqual(registry.opened, ["10.0.0.1"])
        self.assertIn("CONNECTION_TIMEOUT", result["message"])
        self.assertNotIn("Could not open a device session", result["message"])
        self.assertEqual(self._states(), ("pending_apply", "pending_apply"))

    def test_managed_push_and_reconciliation_share_one_host_operation(self) -> None:
        registry = _ManagedSessionRegistry(self.connector)
        controller = InterfaceViewPushController(self.db, registry)

        result = controller.push("10.0.0.1", "all")

        self.assertTrue(result["ok"], result)
        self.assertEqual(registry.execute_calls, 1)
        self.assertTrue(result["reconciliation"]["ok"])
        self.assertEqual(self.db.reconciliations, [("10.0.0.1", self.connector)])

    def test_removed_interface_is_deleted_only_after_success(self) -> None:
        with closing(self.db._connect()) as connection:
            connection.execute("UPDATE t02_interface_name SET sync_status = 'pending_delete';")
            connection.execute("UPDATE t02_router_iface_l3 SET sync_status = 'pending_delete';")
            connection.commit()

        preview = self.controller.preview("10.0.0.1", "all")
        self.assertIn("no ip address", preview["commands"])
        self.assertIn("shutdown", preview["commands"])
        result = self.controller.push("10.0.0.1", "all")
        self.assertTrue(result["ok"], result)
        with closing(self.db._connect()) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM t02_interface_name;"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_wan_password_is_redacted_from_preview_tasks_and_device_log(self) -> None:
        with closing(self.db._connect()) as connection:
            iface_id = int(
                connection.execute(
                    "SELECT iface_id FROM t02_interface_name;"
                ).fetchone()[0]
            )
            connection.execute(
                "DELETE FROM t02_router_iface_l3 WHERE iface_id = ?;",
                (iface_id,),
            )
            connection.execute(
                """
                INSERT INTO t02_router_iface_wan(
                    iface_id, encap_type, ppp_auth, ppp_username,
                    ppp_password, sync_status, action_Cfg
                ) VALUES (?, 'ppp', 'chap', 'lab-user', 'lab-secret', 'pending_apply', '11');
                """,
                (iface_id,),
            )
            connection.commit()

        preview = self.controller.preview("10.0.0.1", "all")
        self.assertNotIn("lab-secret", str(preview))
        self.assertIn("ppp chap password <redacted>", preview["commands"])
        self.connector.connection.output = "ppp chap password 0 lab-secret"
        result = self.controller.push("10.0.0.1", "all")
        self.assertTrue(result["ok"], result)
        self.assertNotIn("lab-secret", str(result))


if __name__ == "__main__":
    unittest.main()
