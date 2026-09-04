from __future__ import annotations

import unittest
from types import SimpleNamespace

from features.devices.post_push_service import PostPushService


class _Connection:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def save_config(self, **kwargs):
        self.calls.append(kwargs)
        return "Copy complete."


class _Connector:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.events: list[str] = []

    def collect_running_config(self):
        self.events.append("collect")
        return {
            "ok": True,
            "running_config": "hostname r1\n",
            "interface_brief": "GigabitEthernet0/0 192.0.2.1 YES manual up up",
        }

    def collect_switch_state(self, state_keys=None):
        self.events.append("switch:" + ",".join(state_keys or ("all",)))
        return {"ok": True, "outputs": {}}


class PostPushServiceTests(unittest.TestCase):
    def test_copies_then_collects_backs_up_and_force_syncs(self) -> None:
        events: list[tuple] = []
        connector = _Connector()
        backup = SimpleNamespace(
            save_snapshot=lambda host, config: (
                events.append(("backup", host, config))
                or {"ok": True, "commitId": "abc"}
            )
        )
        sync = SimpleNamespace(
            sync_manual_snapshot=lambda *args, **kwargs: (
                events.append(("sync", args, kwargs))
                or {"ok": True, "message": "synchronized"}
            )
        )

        result = PostPushService(backup, sync).reconcile("r1", connector)

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["snapshotUpdated"])
        self.assertEqual(
            connector.connection.calls,
            [{"cmd": "copy running-config startup-config", "confirm": True}],
        )
        self.assertEqual(connector.events, ["collect"])
        self.assertEqual(events[0][:2], ("backup", "r1"))
        self.assertEqual(events[1][0], "sync")
        self.assertEqual(events[1][2]["mode"], "force_device_state")

    def test_copy_failure_stops_before_collect_and_sync(self) -> None:
        connector = _Connector()
        connector.connection.save_config = lambda **_kwargs: "% Invalid input detected"
        backup = SimpleNamespace(save_snapshot=lambda *_args: self.fail("backup called"))
        sync = SimpleNamespace(sync_manual_snapshot=lambda *_args, **_kwargs: self.fail("sync called"))

        result = PostPushService(backup, sync).reconcile("r1", connector)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "save")
        self.assertEqual(connector.events, [])

    def test_missing_sync_service_still_saves_and_commits_snapshot(self) -> None:
        connector = _Connector()
        saved: list[tuple[str, str]] = []
        backup = SimpleNamespace(
            save_snapshot=lambda host, config: (
                saved.append((host, config))
                or {"ok": True, "commitId": "abc"}
            )
        )

        result = PostPushService(backup, None).reconcile("r1", connector)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "sync")
        self.assertTrue(result["snapshotUpdated"])
        self.assertEqual(saved, [("r1", "hostname r1\n")])
        self.assertEqual(
            connector.connection.calls,
            [{"cmd": "copy running-config startup-config", "confirm": True}],
        )

    def test_switch_snapshot_collection_is_scoped_or_skipped_by_module(self) -> None:
        sync = SimpleNamespace(
            sync_manual_snapshot=lambda *_args, **_kwargs: {"ok": True}
        )
        backup = SimpleNamespace(
            save_snapshot=lambda *_args: {"ok": True, "commitId": "abc"}
        )
        service = PostPushService(backup, sync, lambda _host: "sw2")

        interfaces_connector = _Connector()
        result = service.reconcile(
            "sw2.local",
            interfaces_connector,
            switch_state_keys=("interfaces_status", "interfaces_trunk"),
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            interfaces_connector.events,
            ["collect", "switch:interfaces_status,interfaces_trunk"],
        )

        stp_connector = _Connector()
        result = service.reconcile(
            "sw2.local", stp_connector, switch_state_keys=()
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(stp_connector.events, ["collect"])


if __name__ == "__main__":
    unittest.main()
