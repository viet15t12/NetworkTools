from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from features.routing.worker import apply_routing_batch_with_connector
from features.routing.view_push import RoutingViewPushController


class _Database:
    def _sync_worker_paths(self) -> None:
        pass

    def _routing_module(self, module: str) -> str:
        return module


class RoutingViewPushControllerTests(unittest.TestCase):
    def test_active_session_batches_all_routing_packages_into_one_transaction(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.calls = []

            def check_enable_mode(self) -> bool:
                return True

            def send_config_set(self, commands, **kwargs):
                self.calls.append((list(commands), dict(kwargs)))
                return "applied"

        class Connector:
            host = "192.0.2.1"
            device_type = "cisco_ios"
            connection = Connection()

        connector = Connector()
        with patch(
            "features.routing.worker.build_cli_routing_commands",
            side_effect=[
                ["no logging console", "no logging monitor", "router ospf 1",
                 "logging console", "logging monitor"],
                ["no logging console", "no logging monitor", "ip route 0.0.0.0 0.0.0.0 1.1.1.1",
                 "logging console", "logging monitor"],
            ],
        ):
            result = apply_routing_batch_with_connector(
                connector,
                [
                    {"sub_type": "ospf", "action": "setup"},
                    {"sub_type": "static", "action": "setup"},
                ],
            )

        self.assertEqual(result, "applied")
        self.assertEqual(len(connector.connection.calls), 1)
        commands, kwargs = connector.connection.calls[0]
        self.assertEqual(commands.count("no logging console"), 1)
        self.assertEqual(commands.count("logging console"), 1)
        self.assertIn("router ospf 1", commands)
        self.assertIn("ip route 0.0.0.0 0.0.0.0 1.1.1.1", commands)
        self.assertEqual(kwargs["read_timeout"], 60)
        self.assertFalse(kwargs["cmd_verify"])

    def test_managed_push_reuses_connector_owned_by_session_lock(self) -> None:
        controller = RoutingViewPushController(_Database(), session_registry=object())
        connector = object()
        captured = {}

        def run(_host, _module, _tasks, provider):
            captured["connector"] = provider("192.0.2.1")
            return {"ok": True, "report": [{"status": "SUCCESS"}]}

        controller._push_tasks_with_provider = run
        result = controller._push_without_reconcile(
            "192.0.2.1", "ospf", [{"target": {"ip": "192.0.2.1"}}], connector
        )

        self.assertTrue(result["ok"])
        self.assertIs(captured["connector"], connector)

    def test_missing_current_report_never_reuses_stale_success(self) -> None:
        controller = RoutingViewPushController(_Database(), session_registry=object())
        controller._session_provider_for_host = lambda _host: object()

        with tempfile.TemporaryDirectory() as temp_dir:
            stale = Path(temp_dir) / "routing_log_ospf_192_0_2_1.json"
            stale.write_text(
                '[{"status": "SUCCESS", "log": "old run"}]',
                encoding="utf-8",
            )
            with (
                patch("infrastructure.network.config.TMP_DIR", temp_dir),
                patch("features.routing.dispatcher.routing_dispatcher"),
            ):
                result = controller.push_tasks(
                    "192.0.2.1", "ospf", [{"target": {"ip": "192.0.2.1"}}]
                )

        self.assertFalse(result["ok"])
        self.assertIn("returned no result", result["message"])


if __name__ == "__main__":
    unittest.main()
