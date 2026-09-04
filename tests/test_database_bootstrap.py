from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import build_databases


APP_DIR = Path(__file__).resolve().parents[1]
SCHEMA_DIR = APP_DIR / "infrastructure" / "database" / "schemas"


class DatabaseBootstrapTests(unittest.TestCase):
    def test_modular_sources_build_valid_sql_directly(self) -> None:
        for source_dir in (SCHEMA_DIR / "device_network", SCHEMA_DIR / "info_collected"):
            with self.subTest(source=source_dir.name):
                script = build_databases.combine_sql(source_dir)
                self.assertIn("CREATE TABLE", script.upper())
                with closing(sqlite3.connect(":memory:")) as connection:
                    connection.executescript(script)

    def test_canonical_device_schema_uses_only_textual_status_columns(self) -> None:
        script = build_databases.combine_sql(SCHEMA_DIR / "device_network")
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.executescript(script)
            tables = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    """
                )
            ]
            columns = {
                table: {
                    row[1]: row[2]
                    for row in connection.execute(f'PRAGMA table_info("{table}")')
                }
                for table in tables
            }

        self.assertEqual(columns["t01_devices"]["connection_status"].upper(), "TEXT")
        sync_columns = [
            table_columns["sync_status"]
            for table_columns in columns.values()
            if "sync_status" in table_columns
        ]
        self.assertGreater(len(sync_columns), 0)
        self.assertTrue(
            all(column_type.upper() == "TEXT" for column_type in sync_columns)
        )
        success_columns = [
            table_columns["success"]
            for table_columns in columns.values()
            if "success" in table_columns
        ]
        self.assertGreater(len(success_columns), 0)
        self.assertTrue(
            all(column_type.upper() == "TEXT" for column_type in success_columns)
        )
        self.assertTrue(
            {
                "t06_vlan_db",
                "t06_interface_l2",
                "t06_iface_port_security",
                "t06_iface_mac_table",
                "t06_etherchannel",
                "t06_stp_config",
                "t06_security_l2",
                "t06_dhcp_trust_ports",
                "t09_vtp_switches",
            }.issubset({table for table, value in columns.items() if "success" in value})
        )
        self.assertNotIn("t06_switch_push_state", tables)
        self.assertNotIn("t06_switch_task_state", tables)

    def test_startup_builds_only_the_missing_runtime_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "schema"
            source_dir.mkdir()
            (source_dir / "01_core.sql").write_text(
                "CREATE TABLE runtime_table (id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )
            db_path = root / "runtime.db"

            output = StringIO()
            with patch.object(
                build_databases,
                "TARGETS",
                ((source_dir, db_path),),
            ), redirect_stdout(output):
                built = build_databases.build_missing_databases()

            self.assertEqual(built, [db_path])
            self.assertEqual(output.getvalue(), "")
            with closing(sqlite3.connect(db_path)) as connection:
                table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_table'"
                ).fetchone()
            self.assertEqual(table, ("runtime_table",))

    def test_startup_preserves_an_existing_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "schema"
            source_dir.mkdir()
            (source_dir / "01_core.sql").write_text(
                "CREATE TABLE replacement (id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )
            db_path = root / "runtime.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute("CREATE TABLE user_data (value TEXT)")
                connection.execute("INSERT INTO user_data VALUES ('keep me')")
                connection.commit()

            with patch.object(
                build_databases,
                "TARGETS",
                ((source_dir, db_path),),
            ):
                built = build_databases.build_missing_databases()

            self.assertEqual(built, [])
            with closing(sqlite3.connect(db_path)) as connection:
                value = connection.execute("SELECT value FROM user_data").fetchone()
                replacement = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='replacement'"
                ).fetchone()
            self.assertEqual(value, ("keep me",))
            self.assertIsNone(replacement)

    def test_startup_repairs_missing_tables_without_losing_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "schema"
            source_dir.mkdir()
            (source_dir / "01_core.sql").write_text(
                "CREATE TABLE first_table (value TEXT);\n"
                "CREATE TABLE second_table (id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )
            db_path = root / "runtime.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute("CREATE TABLE first_table (value TEXT)")
                connection.execute("INSERT INTO first_table VALUES ('keep me')")
                connection.commit()

            with patch.object(build_databases, "TARGETS", ((source_dir, db_path),)):
                report = build_databases.ensure_runtime_databases()

            self.assertEqual(report["statusText"], "DB REPAIRED: 1")
            self.assertEqual(report["repaired"], {"runtime.db": ["second_table"]})
            with closing(sqlite3.connect(db_path)) as connection:
                value = connection.execute("SELECT value FROM first_table").fetchone()
                repaired = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='second_table'"
                ).fetchone()
            self.assertEqual(value, ("keep me",))
            self.assertEqual(repaired, ("second_table",))

    def test_startup_adds_syslog_columns_before_dependent_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "info_collected.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE t12_syslog_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_host TEXT NOT NULL,
                        source_ip TEXT NOT NULL,
                        device_time TEXT,
                        received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        facility TEXT,
                        severity INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 7),
                        mnemonic TEXT,
                        message TEXT NOT NULL,
                        raw_message TEXT,
                        protocol TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
                        parse_status TEXT NOT NULL DEFAULT 'parsed'
                    );
                    CREATE INDEX idx_t12_syslog_host_time
                        ON t12_syslog_messages(device_host, received_at DESC);
                    INSERT INTO t12_syslog_messages (
                        device_host, source_ip, facility, severity, message, protocol
                    ) VALUES ('r1', '192.0.2.1', 'LINK', 3, 'up', 'udp');
                    """
                )
                connection.commit()

            with patch.object(
                build_databases,
                "TARGETS",
                ((build_databases.INFO_COLLECTED_SCHEMA_DIR, db_path),),
            ):
                report = build_databases.ensure_runtime_databases()

            self.assertTrue(report["ok"])
            with closing(sqlite3.connect(db_path)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(t12_syslog_messages)"
                    )
                }
                row = connection.execute(
                    "SELECT device_host, cisco_facility, message "
                    "FROM t12_syslog_messages"
                ).fetchone()
                index = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='idx_t12_syslog_cisco_facility_time'"
                ).fetchone()

            self.assertIn("cisco_facility", columns)
            self.assertIn("syslog_facility", columns)
            self.assertEqual(row, ("r1", "LINK", "up"))
            self.assertEqual(index, ("idx_t12_syslog_cisco_facility_time",))

    def test_legacy_numeric_statuses_migrate_to_text_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "device_network.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE t01_devices (
                        host TEXT PRIMARY KEY,
                        success INTEGER,
                        dev INTEGER DEFAULT 0
                    );
                    CREATE TABLE t04_static_routes (
                        id INTEGER PRIMARY KEY,
                        host TEXT,
                        network TEXT,
                        subnet_mask TEXT,
                        next_hop TEXT,
                        ad INTEGER,
                        success INTEGER
                    );
                    CREATE TABLE t06_vlan_db (
                        id INTEGER PRIMARY KEY,
                        host TEXT,
                        vlan_id INTEGER,
                        vlan_name TEXT
                    );
                    CREATE TABLE t06_svi_interface (
                        id INTEGER PRIMARY KEY,
                        host TEXT,
                        vlan_id INTEGER,
                        success INTEGER
                    );
                    """
                )
                connection.executemany(
                    "INSERT INTO t01_devices(host, success) VALUES (?, ?)",
                    [("down", -1), ("idle", 0), ("up", 1)],
                )
                connection.executemany(
                    """
                    INSERT INTO t04_static_routes
                        (id, host, network, subnet_mask, next_hop, ad, success)
                    VALUES (?, 'up', ?, '255.255.255.0', '192.0.2.1', 1, ?)
                    """,
                    [
                        (1, "10.0.0.0", -1),
                        (2, "10.0.1.0", 0),
                        (3, "10.0.2.0", 1),
                    ],
                )
                connection.execute(
                    "INSERT INTO t06_vlan_db(id, host, vlan_id, vlan_name) "
                    "VALUES (1, 'up', 10, 'VLAN0010')"
                )
                connection.execute(
                    "INSERT INTO t06_svi_interface(id, host, vlan_id, success) "
                    "VALUES (1, 'up', 10, 3)"
                )
                connection.commit()

            migrated = build_databases._migrate_legacy_status_schema(
                SCHEMA_DIR / "device_network", db_path
            )

            self.assertTrue(migrated)
            self.assertTrue(
                db_path.with_name(db_path.name + ".pre-status-migration.bak").is_file()
            )
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT host, connection_status FROM t01_devices ORDER BY host"
                    ).fetchall(),
                    [
                        ("down", "disconnected"),
                        ("idle", "waiting"),
                        ("up", "connected"),
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT sync_status FROM t04_static_routes ORDER BY id"
                    ).fetchall(),
                    [
                        ("pending_delete",),
                        ("pending_apply",),
                        ("synchronized",),
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT sync_status FROM t06_svi_interface"
                    ).fetchone(),
                    ("skipped",),
                )

    def test_canonical_text_success_columns_do_not_trigger_legacy_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "device_network.db"
            build_databases.build_database(
                SCHEMA_DIR / "device_network", db_path
            )

            migrated = build_databases._migrate_legacy_status_schema(
                SCHEMA_DIR / "device_network", db_path
            )

            self.assertFalse(migrated)
            self.assertFalse(
                db_path.with_name(
                    db_path.name + ".pre-status-migration.bak"
                ).exists()
            )

    def test_legacy_status_migration_rejects_unknown_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "device_network.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "CREATE TABLE t01_devices(host TEXT PRIMARY KEY, success INTEGER)"
                )
                connection.execute(
                    "INSERT INTO t01_devices(host, success) VALUES ('bad', 2)"
                )
                connection.commit()

            with self.assertRaisesRegex(
                sqlite3.DatabaseError, "unsupported success value 2"
            ):
                build_databases._migrate_legacy_status_schema(
                    SCHEMA_DIR / "device_network", db_path
                )


if __name__ == "__main__":
    unittest.main()
