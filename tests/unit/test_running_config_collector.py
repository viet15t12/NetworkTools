from __future__ import annotations

import unittest
from unittest.mock import patch

from infrastructure.network.running_config_collector import RunningConfigCollector


class _ChunkedConnection:
    RETURN = "\n"

    def __init__(self) -> None:
        self.prompt = "Router#"
        self.writes: list[str] = []
        self.responses: list[list[str]] = []
        self.current: list[str] = []
        self.config_mode_calls = 0

    def find_prompt(self):
        return self.prompt

    def check_enable_mode(self):
        return True

    def check_config_mode(self):
        return "(config" in self.prompt

    def config_mode(self):
        self.config_mode_calls += 1
        self.prompt = "Router(config)#"

    def clear_buffer(self):
        pass

    def write_channel(self, value):
        self.writes.append(value)
        self.current = self.responses.pop(0)

    def read_channel(self):
        return self.current.pop(0) if self.current else ""

    def is_alive(self):
        return {"is_alive": True}


class RunningConfigCollectorTests(unittest.TestCase):
    def test_waits_for_prompt_across_partial_chunks_and_normalizes_output(self):
        connection = _ChunkedConnection()
        connection.responses = [
            ["terminal length 0\r\n", "Router#"],
            [
                "show running-config\r\nBuilding configuration...\r\n!\r\nversion 17\r\n",
                "interface Gi0/0\r\n description keep ! inline\r\n",
                " ip address 192.0.2.1 255.255.255.0\r\n!\r\nend\r\n\r\n",
                "Router#^@\r\nRouter",
                "#^@",
            ],
        ]

        result = RunningConfigCollector(connection).collect()

        self.assertEqual(
            connection.writes,
            ["terminal length 0\n", "show running-config\n"],
        )
        self.assertEqual(connection.config_mode_calls, 0)
        self.assertIn("interface Gi0/0", result)
        self.assertIn(" ip address 192.0.2.1", result)
        self.assertIn("description keep ! inline", result)
        self.assertTrue(result.endswith("!\nend\n"))
        self.assertNotIn("Router#", result)
        self.assertTrue(result.endswith("\n"))

    def test_stops_waiting_when_device_never_returns_prompt(self):
        connection = _ChunkedConnection()
        connection.responses = [[""]]
        ticks = iter([0.0, 0.0, 0.2])

        with patch(
            "infrastructure.network.running_config_collector.time.monotonic",
            side_effect=lambda: next(ticks),
        ):
            with self.assertRaisesRegex(TimeoutError, "terminal length 0"):
                RunningConfigCollector(
                    connection,
                    read_timeout=0.1,
                    poll_interval=0,
                ).collect()

    def test_accepts_nul_noise_after_prompt_without_waiting_for_timeout(self):
        connection = _ChunkedConnection()
        connection.prompt = "Router(config)#\x00"
        connection.responses = [
            ["do terminal length 0\r\nRouter(config)#\x00"],
            [
                "do show running-config\r\nhostname Router\r\n!\r\nend\r\n\r\n"
                "Router(config)#^@\r\nRouter(config)#^@"
            ],
        ]

        result = RunningConfigCollector(connection, poll_interval=0).collect()

        self.assertEqual(
            connection.writes,
            ["do terminal length 0\n", "do show running-config\n"],
        )
        self.assertEqual(connection.config_mode_calls, 0)
        self.assertIn("hostname Router", result)
        self.assertTrue(result.endswith("!\nend\n"))
        self.assertNotIn("Router(config)", result)
