import tempfile
import unittest
from pathlib import Path

from features.syslog.domain.models import SyslogMessage
from features.syslog.application.log_data import (
    SyslogLogDataService,
    reset_confirmation_phrase,
)
from features.syslog.persistence.message_repository import MessageRepository


def _message(host: str, text: str) -> SyslogMessage:
    return SyslogMessage(
        device_host=host,
        source_ip=host,
        received_at="2026-08-30T01:02:03+00:00",
        severity=5,
        message=text,
        raw_message=text,
        protocol="udp",
        parse_status="parsed",
    )


class SyslogResetRepositoryTests(unittest.TestCase):
    def test_confirmation_phrase_is_explicit_for_host_and_all_scopes(self) -> None:
        self.assertEqual(
            reset_confirmation_phrase("192.0.2.10"), "DELETE 192.0.2.10"
        )
        self.assertEqual(
            reset_confirmation_phrase(""), "DELETE ALL SYSLOG DATA"
        )

    def test_backend_rejects_reset_without_exact_confirmation(self) -> None:
        class Repository:
            def reset_messages(self, host: str = "") -> int:
                raise AssertionError("Repository must not be called")

        result = SyslogLogDataService(Repository()).reset(
            "192.0.2.10", "delete 192.0.2.10"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["deleted"], 0)
        self.assertIn("DELETE 192.0.2.10", result["message"])

    def test_reset_options_and_host_scoped_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "info.db"
            database.touch()
            repository = MessageRepository(database)
            repository.insert_messages([
                _message("192.0.2.10", "first"),
                _message("192.0.2.10", "second"),
                _message("192.0.2.20", "third"),
            ])

            summary = repository.reset_options()
            self.assertEqual(summary["total"], 3)
            self.assertEqual(
                summary["hosts"],
                [
                    {"host": "192.0.2.10", "count": 2},
                    {"host": "192.0.2.20", "count": 1},
                ],
            )
            self.assertEqual(len(repository.messages_for_export("192.0.2.10")), 2)

            backup = SyslogLogDataService(repository).export_scope(
                Path(temporary) / "before-reset.xlsx", "192.0.2.10"
            )
            self.assertTrue(backup["ok"])
            self.assertEqual(backup["count"], 2)
            self.assertTrue(Path(backup["path"]).is_file())

            self.assertEqual(repository.reset_messages("192.0.2.10"), 2)
            self.assertEqual(repository.reset_options()["total"], 1)
            self.assertEqual(
                repository.messages_for_export()[0]["device_host"], "192.0.2.20"
            )

    def test_full_reset_removes_every_message_and_restarts_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "info.db"
            database.touch()
            repository = MessageRepository(database)
            repository.insert_messages([
                _message("192.0.2.10", "first"),
                _message("192.0.2.20", "second"),
            ])

            self.assertEqual(repository.reset_messages(), 2)
            inserted = repository.insert_messages([_message("192.0.2.30", "new")])
            self.assertEqual(inserted[0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
