"""Regression tests for the deliberately small Switching Peewee boundary."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from features.switching.policy_delete_repository import (
    delete_static_mac,
    delete_stp_config,
)
from features.switching.success_repository import mark_task_success
from infrastructure.database.paths import DEVICE_NETWORK_SCHEMA_DIR
from scripts.build_databases import build_database


class _DatabaseAdapter:
    """Expose the same path contract used by the production DB facade."""

    def __init__(self, path: Path) -> None:
        self.db_path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


class SwitchingPeeweePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "device_network.db"
        build_database(DEVICE_NETWORK_SCHEMA_DIR, self.db_path)
        self.db = _DatabaseAdapter(self.db_path)
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.executemany(
                """
                INSERT INTO t01_devices(host, role, device_type)
                VALUES (?, 'sw2', 'switch_layer2');
                """,
                (("sw-a.local",), ("sw-b.local",)),
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_success_acknowledgement_rolls_back_when_later_row_is_missing(self) -> None:
        """No row is acknowledged when one row in the same task is stale."""
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            vlan_id = connection.execute(
                """
                INSERT INTO t06_vlan_db(host, vlan_id, vlan_name)
                VALUES ('sw-a.local', 10, 'users');
                """
            ).lastrowid

        with self.assertRaisesRegex(ValueError, "no longer exists"):
            mark_task_success(
                self.db,
                {
                    "success_rows": [
                        {"kind": "vlan", "id": vlan_id},
                        {"kind": "stp", "id": 999_999},
                    ]
                },
            )

        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            status = connection.execute(
                "SELECT success FROM t06_vlan_db WHERE id = ?;", (vlan_id,)
            ).fetchone()[0]
        self.assertEqual(status, "pending_apply")

    def test_policy_deletion_cannot_cross_the_selected_host(self) -> None:
        """Peewee filters retain the previous host-ownership protection."""
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            stp_id = connection.execute(
                """
                INSERT INTO t06_stp_config(host, vlan_id)
                VALUES ('sw-b.local', 20);
                """
            ).lastrowid
            iface_id = connection.execute(
                """
                INSERT INTO t06_interface_l2(host, if_name)
                VALUES ('sw-b.local', 'GigabitEthernet0/1');
                """
            ).lastrowid
            mac_id = connection.execute(
                """
                INSERT INTO t06_iface_mac_table(
                    iface_id, mac_addr, vlan_id, mac_type
                ) VALUES (?, '0011.2233.4455', 20, 'static');
                """,
                (iface_id,),
            ).lastrowid

        self.assertFalse(delete_stp_config(self.db, "sw-a.local", stp_id)["ok"])
        self.assertFalse(delete_static_mac(self.db, "sw-a.local", mac_id)["ok"])
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            statuses = (
                connection.execute(
                    "SELECT success FROM t06_stp_config WHERE id = ?;", (stp_id,)
                ).fetchone()[0],
                connection.execute(
                    "SELECT success FROM t06_iface_mac_table WHERE id = ?;", (mac_id,)
                ).fetchone()[0],
            )
        self.assertEqual(statuses, ("pending_apply", "pending_apply"))

    def test_success_acknowledgement_updates_compatibility_fields(self) -> None:
        """Lifecycle fields that describe one entity change together."""
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            channel_id = connection.execute(
                """
                INSERT INTO t06_etherchannel(
                    host, po_number, cleanup_member_ports
                ) VALUES ('sw-a.local', 7, 'GigabitEthernet0/9');
                """
            ).lastrowid
            iface_id = connection.execute(
                """
                INSERT INTO t06_interface_l2(host, if_name)
                VALUES ('sw-a.local', 'GigabitEthernet0/2');
                """
            ).lastrowid
            connection.execute(
                """
                INSERT INTO t06_iface_port_security(iface_id)
                VALUES (?);
                """,
                (iface_id,),
            )

        mark_task_success(
            self.db,
            {
                "success_rows": [
                    {"kind": "etherchannel", "id": channel_id},
                    {"kind": "port_security", "id": iface_id},
                ]
            },
        )

        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            channel = connection.execute(
                """
                SELECT success, device_present, cleanup_member_ports
                FROM t06_etherchannel WHERE id = ?;
                """,
                (channel_id,),
            ).fetchone()
            security = connection.execute(
                """
                SELECT success, sync_status
                FROM t06_iface_port_security WHERE iface_id = ?;
                """,
                (iface_id,),
            ).fetchone()
        self.assertEqual(channel, ("synchronized", 1, ""))
        self.assertEqual(security, ("synchronized", "synchronized"))


if __name__ == "__main__":
    unittest.main()
