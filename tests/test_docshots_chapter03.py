"""Chapter 3 contracts: safe workflow, repeatability, and book output path."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docshots.cli import APP_DIR, build_parser, main
from docshots.shots import CHAPTER_03_FILENAMES


class Chapter03DocshotTests(unittest.TestCase):
    def test_cli_ignores_legacy_destination_for_chapter_03(self):
        self.assertEqual(build_parser().parse_args(["chapter-03"]).shot, "chapter-03")
        expected = APP_DIR / "book" / "figures" / "gui" / "chapter-03"
        with patch("docshots.cli.ensure_output_directory", return_value=expected) as mkdir, \
             patch("docshots.chapter03.render_chapter_03_workflow", return_value=()) as render:
            self.assertEqual(main(["chapter-03", "--output-dir", "/unused/legacy"]), 0)
        mkdir.assert_called_once_with(expected)
        self.assertEqual(render.call_args.args[0].output_dir, expected)

    def test_workflow_is_repeatable_and_keeps_backends_isolated(self):
        # Separate processes reproduce the normal CLI lifecycle. The renderer
        # asserts real QML actions and blocks socket connects/external processes.
        code = '''
import sys
from pathlib import Path
from docshots.runtime import RenderRequest
from docshots.chapter03 import render_chapter_03_workflow
render_chapter_03_workflow(RenderRequest(1600, 1000, 2, "light", Path(sys.argv[1])))
'''
        with tempfile.TemporaryDirectory(prefix="chapter03-test-") as directory:
            root = Path(directory)
            for name in ("first", "second"):
                completed = subprocess.run(
                    [sys.executable, "-c", code, str(root / name)],
                    cwd=APP_DIR, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            expected = set(CHAPTER_03_FILENAMES) | {"09-status-details.png"}
            self.assertEqual({p.name for p in (root / "first").glob("*.png")}, expected)
            for name in expected:
                first = (root / "first" / name).read_bytes()
                second = (root / "second" / name).read_bytes()
                self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest(), name)
            self.assertFalse(list(root.glob(".chapter03-*")))

    def test_offline_training_package_is_reproducible_and_navigable(self):
        code = r'''
import importlib.util, sqlite3, sys
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import pyqtSlot
from docshots import runtime as rt
spec = importlib.util.spec_from_file_location("training", "book/fixtures/chapter-03/build_fixture.py")
training = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training)
root = Path(sys.argv[1])
first = training.build_fixture(root / "first.ntp")
second = training.build_fixture(root / "second.ntp")
assert first.read_bytes() == second.read_bytes(), "Training package is not deterministic"
class CountingTerminal(rt.DocumentationTerminal):
    requests = 0
    @pyqtSlot(str, result=bool)
    def hasDeviceSession(self, host):
        self.requests += 1
        return False
    @pyqtSlot(str, result=bool)
    def openDeviceSessionAsync(self, host):
        self.requests += 1
        return False
app = rt._application()
request = rt.RenderRequest(1600, 1000, 1, "light", root)
service = training.WorkspaceService()
session = service.open_project(first)
with patch("socket.socket.connect", side_effect=OSError("Network disabled")), rt.FixtureBundle(request) as fixture:
    with sqlite3.connect(session.device_network_db) as source, sqlite3.connect(fixture.device_db) as target:
        source.backup(target)
    fixture.cli = CountingTerminal()
    engine, window = rt._load_prepared_window(fixture, "Main", rt.ShotSpec("training", "Main", "Offline Lab"), request)
    try:
        sidebar = window.findChild(rt.QObject, "mainPanelSideBar")
        features = window.findChild(rt.QObject, "mainFeatureBar")
        tabs = window.findChild(rt.QObject, "mainDeviceTabs")
        for host in ("192.0.2.1", "192.0.2.11", "192.0.2.13"):
            sidebar.activateDevice(host)
            rt._wait_for_stable_scene(app, engine, window, request.timeout_ms)
            assert tabs.property("activeUid") == host
            assert features.isEnabled()
        assert fixture.cli.requests == 0, "Offline navigation requested a session"
    finally:
        rt._dispose_qml_window(app, engine, window)
service.close_project(session)
'''
        with tempfile.TemporaryDirectory(prefix="chapter03-training-test-") as directory:
            completed = subprocess.run(
                [sys.executable, "-c", code, directory], cwd=APP_DIR,
                capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
