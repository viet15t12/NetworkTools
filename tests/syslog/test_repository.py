import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from features.syslog.repository import SyslogRepository


class SyslogRepositoryTests(unittest.TestCase):
    @staticmethod
    def _create_databases(root: Path) -> tuple[Path, Path]:
        info_db = root / "info.db"
        device_db = root / "devices.db"
        sqlite3.connect(info_db).close()
        with closing(sqlite3.connect(device_db)) as conn:
            with conn:
                conn.execute(
                    "CREATE TABLE t01_devices "
                    "(host TEXT, device_name TEXT, device_type TEXT, "
                    "os TEXT, connection_status TEXT)"
                )
        return info_db, device_db

    def test_schema_migration_preserves_existing_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            info_db = root / "info.db"
            device_db = root / "devices.db"
            with closing(sqlite3.connect(info_db)) as conn:
                with conn:
                    conn.execute("CREATE TABLE legacy_data (value TEXT)")
                    conn.execute("INSERT INTO legacy_data VALUES ('kept')")
            with closing(sqlite3.connect(device_db)) as conn:
                with conn:
                    conn.execute(
                        "CREATE TABLE t01_devices "
                        "(host TEXT, device_name TEXT, device_type TEXT, "
                        "os TEXT, connection_status TEXT)"
                    )

            SyslogRepository(info_db, device_db)

            with closing(sqlite3.connect(info_db)) as conn:
                self.assertEqual(
                    conn.execute("SELECT value FROM legacy_data").fetchone()[0],
                    "kept",
                )
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='table' AND name='t12_syslog_messages'"
                    ).fetchone()
                )
                self.assertIsNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='t12_syslog_device_state'"
                    ).fetchone()
                )
            with closing(sqlite3.connect(device_db)) as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='t10_syslog_servers'"
                    ).fetchone()
                )

    def test_legacy_info_configuration_is_migrated_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            with closing(sqlite3.connect(info_db)) as conn:
                conn.execute(
                    """CREATE TABLE t12_syslog_device_state (
                       device_host TEXT, server_ip TEXT, protocol TEXT, port INTEGER,
                       configured INTEGER, last_result TEXT, updated_at TEXT,
                       PRIMARY KEY(device_host, server_ip, protocol, port))"""
                )
                conn.execute(
                    "INSERT INTO t12_syslog_device_state VALUES "
                    "('192.0.2.1', '192.0.2.100', 'udp', 5514, 1, 'old', NULL)"
                )
                conn.commit()

            repository = SyslogRepository(info_db, device_db)
            rows = repository.device_configurations("192.0.2.1")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["trap_severity"], 5)

            repository.delete_configuration_record(
                "192.0.2.1", "192.0.2.100", "udp", 5514
            )
            repository = SyslogRepository(info_db, device_db)
            self.assertEqual(repository.device_configurations("192.0.2.1"), [])

    def test_failed_cancel_attempt_preserves_existing_configured_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            repository = SyslogRepository(info_db, device_db)
            repository.save_device_state(
                "192.0.2.1",
                "192.0.2.100",
                "udp",
                5514,
                "GigabitEthernet0/0",
                True,
                "configured",
            )

            repository.save_device_attempt(
                "192.0.2.1", "192.0.2.100", "udp", 5514, "removal not verified"
            )

            with closing(sqlite3.connect(device_db)) as conn:
                row = conn.execute(
                    "SELECT configured, last_result FROM t10_syslog_servers"
                ).fetchone()
            self.assertEqual(row, (1, "removal not verified"))

    def test_first_failed_cancel_attempt_does_not_invent_configured_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            repository = SyslogRepository(info_db, device_db)

            repository.save_device_attempt(
                "192.0.2.1", "192.0.2.100", "udp", 5514, "removal failed"
            )

            with closing(sqlite3.connect(device_db)) as conn:
                row = conn.execute(
                    "SELECT configured, last_result FROM t10_syslog_servers"
                ).fetchone()
            self.assertEqual(row, (0, "removal failed"))

    def test_multiple_device_configurations_are_persisted_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            repository = SyslogRepository(info_db, device_db)

            first = {
                "server_ip": "192.0.2.100",
                "protocol": "udp",
                "port": 514,
                "source_interface": "Loopback0",
                "trap_severity": 4,
                "timestamps": True,
                "sequence_numbers": True,
            }
            second = {
                **first,
                "server_ip": "192.0.2.101",
                "protocol": "tcp",
                "port": 5514,
                "source_interface": "GigabitEthernet0/0",
                "trap_severity": 6,
            }

            self.assertTrue(repository.save_configuration("192.0.2.1", first)["ok"])
            self.assertTrue(repository.save_configuration("192.0.2.1", second)["ok"])
            rows = repository.device_configurations("192.0.2.1")

            self.assertEqual(len(rows), 2)
            self.assertEqual({row["server_ip"] for row in rows}, {"192.0.2.100", "192.0.2.101"})
            self.assertTrue(all(row["sync_status"] == "pending_apply" for row in rows))

    def test_new_configuration_defaults_to_listener_port_and_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            repository = SyslogRepository(info_db, device_db)

            result = repository.save_configuration(
                "192.0.2.1",
                {"server_ip": "192.0.2.100", "source_interface": "Loopback0"},
            )

            self.assertTrue(result["ok"], result)
            row = repository.device_configurations("192.0.2.1")[0]
            self.assertEqual(row["port"], 5514)
            self.assertEqual(row["trap_severity"], 5)

    def test_editing_applied_destination_stages_old_server_for_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            info_db, device_db = self._create_databases(Path(temp_dir))
            repository = SyslogRepository(info_db, device_db)
            repository.save_device_state(
                "192.0.2.1", "192.0.2.100", "udp", 514,
                "Loopback0", True, "configured",
            )

            result = repository.save_configuration(
                "192.0.2.1",
                {
                    "server_ip": "192.0.2.101",
                    "protocol": "tcp",
                    "port": 5514,
                    "source_interface": "Loopback0",
                    "trap_severity": 5,
                    "timestamps": True,
                    "sequence_numbers": False,
                    "original_server_ip": "192.0.2.100",
                    "original_protocol": "udp",
                    "original_port": 514,
                },
            )

            self.assertTrue(result["ok"], result)
            rows = repository.device_configurations("192.0.2.1")
            states = {row["server_ip"]: row["sync_status"] for row in rows}
            self.assertEqual(
                states,
                {"192.0.2.100": "pending_delete", "192.0.2.101": "pending_apply"},
            )


if __name__ == "__main__":
    unittest.main()
