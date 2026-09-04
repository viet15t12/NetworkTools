from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dulwich.repo import Repo

from features.config_backup.repository import (
    METADATA_DIRECTORY,
    ConfigBackupRepository,
)
from features.config_backup.paths import repository_path


class ConfigBackupRepositoryTests(unittest.TestCase):
    """Verify per-host Git history without requiring a network device."""

    def test_commits_changed_and_unchanged_snapshots(self) -> None:
        """Every collection creates a commit and preserves changed metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ConfigBackupRepository(Path(temp_dir) / "backup")
            first = repository.commit_snapshot("10.2.3.1", "hostname router", timestamp=1_700_000_000)
            second = repository.commit_snapshot("10.2.3.1", "hostname router", timestamp=1_700_000_001)

            self.assertTrue(first["commitCreated"])
            self.assertTrue(first["changed"])
            self.assertTrue(second["commitCreated"])
            self.assertFalse(second["changed"])
            history = repository.list_commits("10.2.3.1")
            self.assertEqual(len(history), 2)
            self.assertFalse(history[0]["changed"])
            latest_file = Path(second["path"])
            latest_file.write_text("uncommitted working tree\n", encoding="utf-8")
            self.assertEqual(repository.read_commit("10.2.3.1", first["commitId"])["content"], "hostname router\n")

    def test_hosts_are_isolated_and_invalid_hosts_are_rejected(self) -> None:
        """Separate hosts never share history and traversal input fails closed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ConfigBackupRepository(Path(temp_dir) / "backup")
            repository.commit_snapshot("router-a", "hostname a")
            repository.commit_snapshot("router-b", "hostname b")
            self.assertEqual(repository.read_latest("router-a")["content"], "hostname a\n")
            self.assertEqual(repository.read_latest("router-b")["content"], "hostname b\n")
            with self.assertRaises(ValueError):
                repository.commit_snapshot("../escape", "invalid")

    def test_diff_compares_adjacent_or_multi_version_history_ranges(self) -> None:
        """Diff endpoints may span multiple Git snapshots without checkout."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ConfigBackupRepository(Path(temp_dir) / "backup")
            first = repository.commit_snapshot(
                "10.2.3.1",
                "hostname edge\ninterface Loopback0\n description old\n",
                timestamp=1_700_000_000,
            )
            repository.commit_snapshot(
                "10.2.3.1",
                "hostname edge\ninterface Loopback0\n description middle\n",
                timestamp=1_700_000_001,
            )
            third = repository.commit_snapshot(
                "10.2.3.1",
                "hostname edge-new\ninterface Loopback0\n description current\n",
                timestamp=1_700_000_002,
            )

            result = repository.diff_commits(
                "10.2.3.1",
                first["commitId"],
                third["commitId"],
            )

            self.assertTrue(result["ok"])
            self.assertTrue(result["changed"])
            self.assertEqual(result["versionSpan"], 3)
            self.assertEqual(result["additions"], 2)
            self.assertEqual(result["deletions"], 2)
            self.assertIn("-hostname edge", result["diff"])
            self.assertIn("+hostname edge-new", result["diff"])
            self.assertIn("- description old", result["diff"])
            self.assertIn("+ description current", result["diff"])

            identical = repository.diff_commits(
                "10.2.3.1",
                third["commitId"],
                third["commitId"],
            )
            self.assertFalse(identical["changed"])
            self.assertEqual(identical["diff"], "")
            self.assertEqual(identical["versionSpan"], 1)

    def test_legacy_dot_git_metadata_is_migrated_without_losing_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_root = Path(temp_dir) / "backup"
            path = repository_path(backup_root, "10.2.3.1")
            path.mkdir(parents=True)
            Repo.init(path).close()

            repository = ConfigBackupRepository(backup_root)
            repository.ensure_repository("10.2.3.1")

            self.assertFalse((path / ".git").exists())
            self.assertTrue((path / METADATA_DIRECTORY).is_dir())
            committed = repository.commit_snapshot("10.2.3.1", "hostname migrated")
            self.assertTrue(committed["ok"])


if __name__ == "__main__":
    unittest.main()
