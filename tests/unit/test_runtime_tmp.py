from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from infrastructure.system.runtime_tmp import cleanup_runtime_tmp


class RuntimeTmpCleanupTests(unittest.TestCase):
    def test_cleanup_removes_all_contents_and_preserves_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "tmp"
            nested = root / "nested"
            nested.mkdir(parents=True)
            (root / "output.json").write_text("{}", encoding="utf-8")
            (nested / "inventory.yaml").write_text("hosts: {}", encoding="utf-8")

            errors = cleanup_runtime_tmp(root)

            self.assertEqual(errors, ())
            self.assertTrue(root.is_dir())
            self.assertEqual(list(root.iterdir()), [])

    def test_cleanup_accepts_a_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing"

            self.assertEqual(cleanup_runtime_tmp(missing), ())

    def test_cleanup_unlinks_symlink_without_touching_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "tmp"
            target = base / "outside"
            root.mkdir()
            target.mkdir()
            protected = target / "keep.txt"
            protected.write_text("keep", encoding="utf-8")
            try:
                (root / "linked").symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks are unavailable on this platform")

            errors = cleanup_runtime_tmp(root)

            self.assertEqual(errors, ())
            self.assertTrue(protected.is_file())
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
