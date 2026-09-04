from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.terminal as runtime
from core.terminal import TerminalHelper
from features.config_backup.service import ConfigBackupService


class ConfigBackupFlowTests(unittest.TestCase):
    """Exercise legacy migration and service payloads across the storage boundary."""

    def test_legacy_backup_is_imported_once_and_preserved(self) -> None:
        """Repeated reads keep one import commit and retain the migrated source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_root = Path(temp_dir) / "backup"
            legacy_dir = backup_root / "10.2.3.1"
            legacy_dir.mkdir(parents=True)
            legacy = legacy_dir / "10.2.3.1_running-config.txt"
            legacy.write_text("hostname legacy\n", encoding="utf-8")
            service = ConfigBackupService(backup_root)

            first = service.list_history("10.2.3.1")
            second = service.list_history("10.2.3.1")

            self.assertTrue(first["ok"])
            self.assertEqual(len(first["commits"]), 1)
            self.assertEqual(len(second["commits"]), 1)
            self.assertFalse(legacy.exists())
            self.assertTrue(legacy.with_name(f"{legacy.name}.migrated").exists())
            self.assertEqual(service.read_latest("10.2.3.1")["content"], "hostname legacy\n")

    def test_terminal_backup_collects_commits_then_synchronizes(self) -> None:
        """The application flow commits collected text before DB state synchronization."""
        class FakeConnector:
            def collect_running_config(self) -> dict[str, object]:
                return {
                    "ok": True,
                    "running_config": "hostname integrated\n",
                    "interface_brief": "GigabitEthernet0/0 up up\n",
                }

        class FakeSyncService:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, str, dict[str, object]]] = []

            def sync_committed_snapshot(
                self,
                host: str,
                running_config: str,
                interface_brief: str,
                commit_result: dict[str, object],
            ) -> dict[str, object]:
                self.calls.append((host, running_config, interface_brief, commit_result))
                return {
                    "ok": True,
                    "attempted": True,
                    "skipped": False,
                    "reason": "synchronized",
                    "summary": {"interfaces": 1, "ospf_processes": 0},
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            service = ConfigBackupService(Path(temp_dir) / "backup")
            sync_service = FakeSyncService()
            helper = TerminalHelper(
                config_backup_service=service,
                config_sync_service=sync_service,
            )
            connector = FakeConnector()
            device = {
                "host": "10.2.3.1",
                "method": "ssh",
                "port": 22,
                "username": "user",
                "password": "password",
                "device_type": "cisco_ios",
                "dev": 0,
            }
            with patch.object(runtime.device_login_service, "load", return_value=device), patch.object(
                runtime.device_session_registry,
                "get_connector",
                return_value=connector,
            ):
                result = helper.saveRunningConfigBackup("10.2.3.1")

            self.assertTrue(result["ok"])
            self.assertTrue(result["commitCreated"])
            self.assertEqual(len(sync_service.calls), 1)
            self.assertTrue(sync_service.calls[0][3]["changed"])
            self.assertEqual(service.read_latest("10.2.3.1")["content"], "hostname integrated\n")

    def test_service_returns_structured_diff_failures(self) -> None:
        """Invalid Diff endpoints stay inside the stable UI payload contract."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ConfigBackupService(Path(temp_dir) / "backup")
            commit = service.save_snapshot("10.2.3.1", "hostname edge\n")

            result = service.diff_commits(
                "10.2.3.1",
                commit["commitId"],
                "not-a-commit",
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["diff"], "")
            self.assertIn("40 hexadecimal", result["message"])

    def test_manual_sys_previews_before_explicit_force_apply(self) -> None:
        class FakeConnector:
            def collect_running_config(self):
                return {
                    "ok": True,
                    "running_config": "hostname preview\n",
                    "interface_brief": "",
                }

        class FakeSyncService:
            def __init__(self):
                self.modes = []

            def preview_manual_snapshot(self, *_args):
                self.modes.append("preview")
                return {
                    "ok": True,
                    "reason": "manual-preview",
                    "summary": {
                        "mode": "preview",
                        "conflicts": ["ospf"],
                        "interfaces": 0,
                        "static_routes": 0,
                        "default_routes": 0,
                        "ospf_processes": 1,
                        "eigrp_processes": 0,
                    },
                }

            def sync_manual_snapshot(self, *_args, mode="safe"):
                self.modes.append(mode)
                return {
                    "ok": True,
                    "reason": "manual-synchronized",
                    "summary": {"mode": mode, "conflicts": []},
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            sync = FakeSyncService()
            helper = TerminalHelper(
                config_backup_service=ConfigBackupService(Path(temp_dir) / "backup"),
                config_sync_service=sync,
            )
            device = {
                "host": "10.2.3.1",
                "method": "ssh",
                "port": 22,
                "username": "user",
                "password": "password",
                "device_type": "cisco_ios",
                "dev": 0,
            }
            with patch.object(runtime.device_login_service, "load", return_value=device), patch.object(
                runtime.device_session_registry, "get_connector", return_value=FakeConnector()
            ):
                preview = helper.manualSyncSys("10.2.3.1")
                applied = helper.applyManualSyncSys(
                    "10.2.3.1", "force_device_state"
                )
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["sync"]["summary"]["conflicts"], ["ospf"])
        self.assertTrue(applied["ok"])
        self.assertEqual(sync.modes, ["preview", "force_device_state"])


if __name__ == "__main__":
    unittest.main()
