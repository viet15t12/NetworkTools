from __future__ import annotations

import unittest

from features.syslog.models import ListenerConfig
from features.syslog.pipeline import SyslogPipeline


class _Writer:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self, timeout: float = 5.0) -> None:
        self.stopped += 1

    def submit(self, *_args) -> None:
        pass


class _Receiver:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.started = 0
        self.stopped = 0

    @property
    def is_running(self) -> bool:
        return self.started > 0 and self.stopped == 0

    def start(self) -> None:
        self.started += 1
        if self.should_fail:
            raise OSError("address already in use")

    def stop(self, timeout: float = 3.0) -> None:
        self.stopped += 1


class SyslogPipelineTests(unittest.TestCase):
    def test_receiver_start_failure_rolls_back_writer(self) -> None:
        writer = _Writer()
        receiver = _Receiver(should_fail=True)
        pipeline = SyslogPipeline(
            writer, lambda _message: None, receiver_factory=lambda *_: receiver
        )

        with self.assertRaisesRegex(OSError, "address already in use"):
            pipeline.start(ListenerConfig("127.0.0.1", "127.0.0.1", 5514, "udp"))

        self.assertEqual(writer.started, 1)
        self.assertEqual(writer.stopped, 1)
        self.assertGreaterEqual(receiver.stopped, 1)
        self.assertIsNone(pipeline.receiver)

    def test_repeated_start_reuses_running_receiver(self) -> None:
        writer = _Writer()
        receiver = _Receiver()
        pipeline = SyslogPipeline(
            writer, lambda _message: None, receiver_factory=lambda *_: receiver
        )
        config = ListenerConfig("127.0.0.1", "127.0.0.1", 5514, "udp")

        self.assertIs(pipeline.start(config), receiver)
        self.assertIs(pipeline.start(config), receiver)
        pipeline.stop()

        self.assertEqual(writer.started, 1)
        self.assertEqual(writer.stopped, 1)
        self.assertEqual(receiver.started, 1)
        self.assertEqual(receiver.stopped, 1)


if __name__ == "__main__":
    unittest.main()
