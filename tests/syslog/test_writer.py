from __future__ import annotations

import threading
import unittest

from features.syslog.writer import SyslogWriter


class _Repository:
    def __init__(self) -> None:
        self.resolve_calls = 0
        self.inserted = []

    def resolve_device_host(self, source_ip: str) -> str:
        self.resolve_calls += 1
        return "router-1"

    def insert_messages(self, messages):
        rows = list(messages)
        self.inserted.extend(rows)
        return [row.to_dict() for row in rows]


class SyslogWriterTests(unittest.TestCase):
    def test_batches_messages_and_caches_source_mapping(self) -> None:
        repository = _Repository()
        published = threading.Event()
        errors: list[str] = []
        writer = SyslogWriter(
            repository,
            lambda _rows: published.set(),
            errors.append,
        )
        writer.start()
        try:
            writer.submit(b"first", "192.0.2.1", "udp")
            writer.submit(b"second", "192.0.2.1", "udp")
            self.assertTrue(published.wait(2.0))
        finally:
            writer.stop()

        self.assertEqual(len(repository.inserted), 2)
        self.assertEqual(repository.resolve_calls, 1)
        self.assertEqual(writer.dropped, 0)
        self.assertEqual(errors, [])

    def test_publish_failure_does_not_mark_committed_rows_as_dropped(self) -> None:
        repository = _Repository()
        error_seen = threading.Event()

        def publish(_rows) -> None:
            raise RuntimeError("UI is gone")

        def report_error(_message: str) -> None:
            error_seen.set()

        writer = SyslogWriter(repository, publish, report_error)
        writer.start()
        try:
            writer.submit(b"stored", "192.0.2.2", "udp")
            self.assertTrue(error_seen.wait(2.0))
        finally:
            writer.stop()

        self.assertEqual(len(repository.inserted), 1)
        self.assertEqual(writer.dropped, 0)


if __name__ == "__main__":
    unittest.main()
