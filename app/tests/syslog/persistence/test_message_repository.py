import sqlite3
import tempfile
import unittest
from pathlib import Path

from features.syslog.domain.models import SyslogMessage
from features.syslog.persistence.message_repository import MessageRepository


class MessageRepositoryV2Tests(unittest.TestCase):
    def test_migrates_legacy_columns_and_persists_explicit_facilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "info.db"
            with sqlite3.connect(database) as conn:
                conn.execute(
                    """CREATE TABLE t12_syslog_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, device_host TEXT NOT NULL,
                    source_ip TEXT NOT NULL, device_time TEXT, received_at TEXT NOT NULL,
                    facility TEXT, severity INTEGER NOT NULL, mnemonic TEXT,
                    message TEXT NOT NULL, raw_message TEXT, protocol TEXT NOT NULL,
                    parse_status TEXT NOT NULL)"""
                )
                conn.execute(
                    """INSERT INTO t12_syslog_messages
                    (device_host, source_ip, received_at, facility, severity, message,
                     protocol, parse_status) VALUES ('r1', '192.0.2.1',
                     CURRENT_TIMESTAMP, 'SYS', 5, 'legacy', 'udp', 'parsed')"""
                )

            repository = MessageRepository(database)
            inserted = repository.insert_messages([SyslogMessage(
                source_ip="192.0.2.1", device_host="r1", protocol="udp",
                severity=3, message="down", raw_message="raw", syslog_pri=189,
                syslog_facility=23, cisco_facility="LINK", mnemonic="UPDOWN",
                sequence_number=12, clock_unsynchronized=True,
            )])
            self.assertEqual(inserted[0]["syslog_facility"], 23)

            rows = repository.query_messages({}, limit=10)
            self.assertEqual(rows[0]["cisco_facility"], "LINK")
            self.assertTrue(rows[0]["clock_unsynchronized"])
            self.assertEqual(rows[1]["cisco_facility"], "SYS")

            repository.insert_messages([SyslogMessage(
                source_ip="192.0.2.2", device_host="r2", protocol="tcp",
                severity=5, message="tcp event", raw_message="tcp event",
            )])
            tcp_rows = repository.query_messages({"protocols": ["tcp"]}, limit=10)
            self.assertEqual(len(tcp_rows), 1)
            self.assertEqual(tcp_rows[0]["protocol"], "tcp")

    def test_filters_time_facility_mnemonic_and_latest_rows_per_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "info.db"
            database.touch()
            repository = MessageRepository(database)
            rows = []
            for host_index, host in enumerate(("r1", "r2")):
                for minute in range(3):
                    rows.append(SyslogMessage(
                        source_ip=f"192.0.2.{host_index + 1}",
                        device_host=host,
                        protocol="udp",
                        severity=3 if minute == 2 else 5,
                        message=f"event {host} {minute}",
                        raw_message="raw",
                        received_at=f"2026-08-26T18:0{minute + host_index}:00+00:00",
                        cisco_facility="LINK" if minute == 2 else "SYS",
                        mnemonic="UPDOWN" if minute == 2 else "CONFIG_I",
                    ))
            repository.insert_messages(rows)

            latest = repository.query_messages({"per_host": 2}, limit=20)
            self.assertEqual(len(latest), 4)
            self.assertEqual(
                {host: sum(row["device_host"] == host for row in latest) for host in ("r1", "r2")},
                {"r1": 2, "r2": 2},
            )

            filtered = repository.query_messages({
                "from_time": "2026-08-26T18:02:00+00:00",
                "to_time": "2026-08-26T18:03:00+00:00",
                "facility": "link",
                "mnemonic": "up",
            }, limit=20)
            self.assertEqual({row["device_host"] for row in filtered}, {"r1", "r2"})
            only_r2 = repository.query_messages({"hosts": ["r2", "missing"]}, limit=20)
            self.assertEqual({row["device_host"] for row in only_r2}, {"r2"})
            self.assertEqual(repository.distinct_hosts(), ["r1", "r2"])


if __name__ == "__main__":
    unittest.main()
