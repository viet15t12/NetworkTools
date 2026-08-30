from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main as _main_bootstrap  # noqa: F401 - configures PyQt paths
from PyQt6.QtGui import QImageReader

from docshots.cli import DEFAULT_OUTPUT_DIR, build_parser, ensure_output_directory
from docshots.runtime import (
    DocumentationTerminal,
    FixtureBundle,
    RenderRequest,
    VLAN_CREATED_ROW,
    VLAN_FIXTURE_HOST,
    VLAN_FIXTURE_ROWS,
)
from docshots.shots import (
    DIALOG_REGRESSION_FILENAMES,
    SHOT_REGISTRY,
    VLAN_WORKFLOW_FILENAMES,
    resolve_shots,
)


APP_DIR = Path(__file__).resolve().parents[1]


class DocshotCliTests(unittest.TestCase):
    def test_parser_defaults_and_overrides(self) -> None:
        defaults = build_parser().parse_args(["welcome"])
        self.assertEqual(defaults.width, 1600)
        self.assertEqual(defaults.height, 1000)
        self.assertEqual(defaults.scale, 2.0)
        self.assertEqual(defaults.theme, "light")
        self.assertEqual(defaults.output_dir, DEFAULT_OUTPUT_DIR)

        custom = build_parser().parse_args(
            ["workspace", "--width", "1200", "--height", "750", "--scale", "1.5", "--theme", "dark"]
        )
        self.assertEqual((custom.width, custom.height, custom.scale), (1200, 750, 1.5))
        self.assertEqual(custom.theme, "dark")
        self.assertEqual(build_parser().parse_args(["vlan"]).shot, "vlan")
        self.assertEqual(build_parser().parse_args(["dialogs"]).shot, "dialogs")

    def test_output_directory_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested" / "gui"
            self.assertEqual(ensure_output_directory(output), output.resolve())
            self.assertTrue(output.is_dir())

    def test_registry_and_all_are_stable(self) -> None:
        self.assertEqual(tuple(SHOT_REGISTRY), ("welcome", "workspace", "devices"))
        self.assertEqual(
            tuple(shot.name for shot in resolve_shots("all")),
            tuple(SHOT_REGISTRY),
        )

    def test_unknown_shot_is_rejected(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["not-a-shot"])
        with self.assertRaisesRegex(ValueError, "Unknown shot"):
            resolve_shots("not-a-shot")

    def test_documentation_terminal_never_starts_network_or_processes(self) -> None:
        terminal = DocumentationTerminal()
        with patch("socket.create_connection") as connect, patch("subprocess.Popen") as popen:
            self.assertTrue(terminal.openDeviceSessionAsync("192.0.2.1"))
            self.assertTrue(terminal.hasDeviceSession("192.0.2.1"))
            self.assertFalse(terminal.connectHostAndSyncAsync("192.0.2.1"))
            connect.assert_not_called()
            popen.assert_not_called()
        terminal.shutdown()
        self.assertTrue(terminal.shut_down)

    def test_vlan_fixture_starts_clean_and_save_creates_pending_vlan_30(self) -> None:
        fixture_pattern = "networktools-docshots-*"
        fixtures_before = set(Path(tempfile.gettempdir()).glob(fixture_pattern))
        with tempfile.TemporaryDirectory() as temporary:
            request = RenderRequest(800, 500, 1, "light", Path(temporary))
            with patch("socket.create_connection") as connect, patch(
                "subprocess.Popen"
            ) as popen, FixtureBundle(request) as fixture:
                rows = fixture.db_manager.getSwitchVlans(VLAN_FIXTURE_HOST)
                self.assertEqual(
                    [(row["vlan_id"], row["vlan_name"], row["state"]) for row in rows],
                    list(VLAN_FIXTURE_ROWS),
                )
                self.assertNotIn(VLAN_CREATED_ROW[0], [row["vlan_id"] for row in rows])

                result = fixture.db_manager.saveSwitchVlan(
                    VLAN_FIXTURE_HOST,
                    {
                        "id": 0,
                        "vlan_id": VLAN_CREATED_ROW[0],
                        "vlan_name": VLAN_CREATED_ROW[1],
                        "state": VLAN_CREATED_ROW[2],
                    },
                )
                self.assertTrue(result["ok"], result)
                created = next(
                    row
                    for row in fixture.db_manager.getSwitchVlans(VLAN_FIXTURE_HOST)
                    if row["vlan_id"] == VLAN_CREATED_ROW[0]
                )
                self.assertEqual(
                    (created["vlan_name"], created["state"], created["success"]),
                    ("Guest", "active", "pending_apply"),
                )
                connect.assert_not_called()
                popen.assert_not_called()
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob(fixture_pattern)),
            fixtures_before,
        )


class DocshotHeadlessTests(unittest.TestCase):
    def test_all_renders_lossless_pngs_at_requested_size(self) -> None:
        fixture_pattern = "networktools-docshots-*"
        fixtures_before = set(Path(tempfile.gettempdir()).glob(fixture_pattern))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gui"
            command = [
                sys.executable,
                str(APP_DIR / "scripts" / "docshots.py"),
                "all",
                "--width",
                "800",
                "--height",
                "500",
                "--scale",
                "1",
                "--output-dir",
                str(output),
            ]
            completed = subprocess.run(
                command,
                cwd=APP_DIR,
                text=True,
                capture_output=True,
                timeout=90,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for name in SHOT_REGISTRY:
                path = output / f"{name}.png"
                self.assertTrue(path.is_file(), path)
                self.assertGreater(path.stat().st_size, 0)
                reader = QImageReader(str(path), b"PNG")
                self.assertTrue(reader.canRead(), reader.errorString())
                self.assertEqual((reader.size().width(), reader.size().height()), (800, 500))
                self.assertFalse(reader.read().isNull(), reader.errorString())
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob(fixture_pattern)),
            fixtures_before,
        )

    def test_vlan_workflow_renders_ordered_pngs_without_leaking_fixture(self) -> None:
        fixture_pattern = "networktools-docshots-*"
        fixtures_before = set(Path(tempfile.gettempdir()).glob(fixture_pattern))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gui"
            command = [
                sys.executable,
                str(APP_DIR / "scripts" / "docshots.py"),
                "vlan",
                "--width",
                "1600",
                "--height",
                "1000",
                "--scale",
                "1",
                "--output-dir",
                str(output),
            ]
            completed = subprocess.run(
                command,
                cwd=APP_DIR,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Created VLAN documentation screenshots:", completed.stdout)
            self.assertEqual(
                tuple(path.name for path in sorted((output / "vlan").glob("*.png"))),
                VLAN_WORKFLOW_FILENAMES,
            )
            for filename in VLAN_WORKFLOW_FILENAMES:
                path = output / "vlan" / filename
                self.assertGreater(path.stat().st_size, 0)
                reader = QImageReader(str(path), b"PNG")
                self.assertTrue(reader.canRead(), reader.errorString())
                self.assertEqual((reader.size().width(), reader.size().height()), (1600, 1000))
                self.assertFalse(reader.read().isNull(), reader.errorString())
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob(fixture_pattern)),
            fixtures_before,
        )

    def test_dialog_regressions_render_composed_popups_at_scale_two(self) -> None:
        fixture_pattern = "networktools-docshots-*"
        fixtures_before = set(Path(tempfile.gettempdir()).glob(fixture_pattern))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dialogs"
            command = [
                sys.executable,
                str(APP_DIR / "scripts" / "docshots.py"),
                "dialogs",
                "--width",
                "1600",
                "--height",
                "1000",
                "--scale",
                "2",
                "--output-dir",
                str(output),
            ]
            completed = subprocess.run(
                command,
                cwd=APP_DIR,
                text=True,
                capture_output=True,
                timeout=240,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(
                "Created dialog regression screenshots:", completed.stdout
            )
            self.assertEqual(
                tuple(path.name for path in sorted(output.glob("*.png"))),
                tuple(sorted(DIALOG_REGRESSION_FILENAMES)),
            )
            expected_sizes = {
                "view-push-dialog.png": (3200, 2000),
                "snapshot-history-dialog.png": (1536, 1276),
                "create-project-dialog.png": (1296, 1066),
                "create-project-password-dialog.png": (1296, 1346),
            }
            for filename in DIALOG_REGRESSION_FILENAMES:
                path = output / filename
                reader = QImageReader(str(path), b"PNG")
                self.assertTrue(reader.canRead(), reader.errorString())
                self.assertEqual(
                    (reader.size().width(), reader.size().height()),
                    expected_sizes[filename],
                )
                self.assertFalse(reader.read().isNull(), reader.errorString())
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob(fixture_pattern)),
            fixtures_before,
        )


if __name__ == "__main__":
    unittest.main()
