from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.terminal import TerminalHelper


class ManualSyncNamingTests(unittest.TestCase):
    def test_canonical_manual_sync_api_is_available(self) -> None:
        self.assertTrue(callable(getattr(TerminalHelper, "manualSync", None)))
        self.assertTrue(callable(getattr(TerminalHelper, "applyManualSync", None)))
        self.assertTrue(callable(getattr(TerminalHelper, "manualSyncAsync", None)))
        self.assertTrue(callable(getattr(TerminalHelper, "applyManualSyncAsync", None)))

    def test_legacy_sys_named_api_delegates_to_corrected_api(self) -> None:
        calls: list[tuple[object, ...]] = []
        facade = SimpleNamespace(
            manualSync=lambda host: calls.append(("preview", host)) or {"ok": True},
            applyManualSync=lambda host, mode: (
                calls.append(("apply", host, mode)) or {"ok": True}
            ),
            manualSyncAsync=lambda host: calls.append(("preview-async", host)) or True,
            applyManualSyncAsync=lambda host, mode: (
                calls.append(("apply-async", host, mode)) or True
            ),
        )

        self.assertTrue(TerminalHelper.manualSyncSys(facade, "r1")["ok"])
        self.assertTrue(TerminalHelper.applyManualSyncSys(facade, "r1", "safe")["ok"])
        self.assertTrue(TerminalHelper.manualSyncSysAsync(facade, "r1"))
        self.assertTrue(
            TerminalHelper.applyManualSyncSysAsync(
                facade, "r1", "force_device_state"
            )
        )
        self.assertEqual(
            calls,
            [
                ("preview", "r1"),
                ("apply", "r1", "safe"),
                ("preview-async", "r1"),
                ("apply-async", "r1", "force_device_state"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
