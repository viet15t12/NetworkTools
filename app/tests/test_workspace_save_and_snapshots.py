from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import infrastructure.workspace.snapshot as snapshot_module

from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from core.welcome import WelcomeController
from infrastructure.database.recent_projects import RecentProjectRepository
from core.workspace_save import WorkspaceSaveController
from features.config_backup.repository import ConfigBackupRepository
from infrastructure.workspace import (
    Argon2Parameters,
    WorkspaceConflictError,
    WorkspacePackageCodec,
    WorkspaceService,
)


def _initialize_test_databases(device_db: Path, collected_db: Path) -> None:
    for path, value in ((device_db, "initial"), (collected_db, "collected")):
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as database:
            database.execute("CREATE TABLE state (value TEXT NOT NULL)")
            database.execute("INSERT INTO state VALUES (?)", (value,))
            database.commit()


class WorkspaceSaveServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.codec = WorkspacePackageCodec(
            encryption_parameters=Argon2Parameters(
                memory_cost_kib=8 * 1024, iterations=1, lanes=1
            )
        )
        self.service = WorkspaceService(
            self.codec, database_initializer=_initialize_test_databases
        )
        self.project = self.root / "Versioned.ntp"
        self.session = self.service.create_project("Versioned", self.project)

    def tearDown(self) -> None:
        self.session.close()
        self.temporary.cleanup()

    def test_autosave_images_live_wal_database_and_creates_snapshot(self) -> None:
        with closing(sqlite3.connect(self.session.device_network_db)) as database:
            database.execute("PRAGMA journal_mode = WAL")
            database.execute("UPDATE state SET value = 'autosaved'")
            database.commit()

            result = self.service.save_project(
                self.session,
                reason="automatic",
                force=False,
                create_snapshot=True,
                snapshot_reason="automatic",
                source_generation=1,
            )

            self.assertFalse(result.skipped)
            self.assertIsNotNone(result.snapshot)
            self.assertFalse(self.project.with_name("Versioned.ntp.tmp").exists())
            self.assertEqual(
                database.execute("SELECT value FROM state").fetchone(),
                ("autosaved",),
            )

        with zipfile.ZipFile(self.project) as archive:
            names = archive.namelist()
            snapshot_id = result.snapshot.snapshot_id
            self.assertIn(f"snapshots/{snapshot_id}/snapshot.json", names)
            self.assertIn(f"snapshots/{snapshot_id}/device_network.db", names)
            self.assertNotIn("device_network.db-wal", names)

        self.session.close()
        with self.service.open_project(self.project) as reopened:
            with closing(sqlite3.connect(reopened.device_network_db)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM state").fetchone(),
                    ("autosaved",),
                )
            snapshots = self.service.list_snapshots(reopened)
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].reason, "automatic")

    def test_unchanged_automatic_save_is_skipped_without_new_history(self) -> None:
        before = self.project.stat().st_mtime_ns

        result = self.service.save_project(
            self.session,
            reason="automatic",
            force=False,
            create_snapshot=True,
            snapshot_reason="automatic",
        )

        self.assertTrue(result.skipped)
        self.assertEqual(self.project.stat().st_mtime_ns, before)
        self.assertEqual(self.service.list_snapshots(self.session), ())

    def test_config_backup_git_history_round_trips_without_dot_git_entries(self) -> None:
        repository = ConfigBackupRepository(self.session.backup_directory)
        repository.commit_snapshot("10.2.3.1", "hostname packaged")
        repository_root = self.session.backup_directory / "10.2.3.1" / "cfg"
        # Reproduce a workspace created by the former repository layout.
        (repository_root / ".cams-git").rename(repository_root / ".git")

        result = self.service.save_project(self.session, reason="shutdown", force=False)

        self.assertFalse(result.skipped)
        with zipfile.ZipFile(self.project) as archive:
            names = archive.namelist()
        self.assertFalse(any(".git" in Path(name).parts for name in names))
        self.assertTrue(any(".cams-git" in Path(name).parts for name in names))

        self.session.close()
        with self.service.open_project(self.project) as reopened:
            reopened_repository = ConfigBackupRepository(reopened.backup_directory)
            self.assertEqual(
                reopened_repository.read_latest("10.2.3.1")["content"],
                "hostname packaged\n",
            )

    def test_external_replacement_is_never_overwritten(self) -> None:
        external_bytes = b"externally replaced project"
        self.project.write_bytes(external_bytes)
        with closing(sqlite3.connect(self.session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'local change'")
            database.commit()

        with self.assertRaises(WorkspaceConflictError):
            self.service.save_project(self.session, reason="manual")

        self.assertEqual(self.project.read_bytes(), external_bytes)

    def test_late_external_change_preserves_verified_tmp_recovery_candidate(self) -> None:
        with closing(sqlite3.connect(self.session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'local late change'")
            database.commit()
        external_bytes = b"late external replacement"
        original_verify = self.codec._verify_package

        def verify_then_replace_target(path, password):
            original_verify(path, password)
            self.project.write_bytes(external_bytes)

        with patch.object(
            self.codec, "_verify_package", side_effect=verify_then_replace_target
        ):
            with self.assertRaises(WorkspaceConflictError):
                self.service.save_project(self.session, reason="manual")

        temporary_package = self.project.with_name("Versioned.ntp.tmp")
        self.assertEqual(self.project.read_bytes(), external_bytes)
        self.assertTrue(zipfile.is_zipfile(temporary_package))

    def test_automatic_snapshot_retention_is_bounded(self) -> None:
        for index in range(21):
            with closing(sqlite3.connect(self.session.device_network_db)) as database:
                database.execute("UPDATE state SET value = ?", (f"state-{index}",))
                database.commit()
            self.service.save_project(
                self.session,
                reason="automatic",
                force=False,
                create_snapshot=True,
                snapshot_reason="automatic",
                source_generation=index + 1,
            )

        snapshots = self.service.list_snapshots(self.session)
        self.assertEqual(len(snapshots), 20)
        self.assertEqual(snapshots[0].source_generation, 21)
        self.assertEqual(snapshots[-1].source_generation, 2)

    def test_snapshot_rollback_creates_pinned_safety_point_and_persists(self) -> None:
        first_save = self.service.save_project(
            self.session,
            reason="snapshot",
            create_snapshot=True,
            snapshot_label="Known good",
            snapshot_reason="manual",
            source_generation=1,
        )
        known_good = first_save.snapshot
        self.assertIsNotNone(known_good)

        with closing(sqlite3.connect(self.session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'changed later'")
            database.commit()
        self.service.save_project(self.session, reason="manual")

        rollback = self.service.rollback_project(
            self.session, known_good.snapshot_id, source_generation=2
        )

        self.assertEqual(rollback.restored_snapshot.snapshot_id, known_good.snapshot_id)
        self.assertTrue(rollback.safety_snapshot.pinned)
        self.assertEqual(rollback.safety_snapshot.reason, "before-rollback")
        with closing(sqlite3.connect(self.session.device_network_db)) as database:
            self.assertEqual(
                database.execute("SELECT value FROM state").fetchone(),
                ("initial",),
            )
        self.session.close()
        with self.service.open_project(self.project) as reopened:
            with closing(sqlite3.connect(reopened.device_network_db)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM state").fetchone(),
                    ("initial",),
                )
            snapshots = self.service.list_snapshots(reopened)
            self.assertTrue(any(item.pinned for item in snapshots))

    def test_failed_rollback_restores_both_live_databases_and_backup_tree(self) -> None:
        known_good = self.service.save_project(
            self.session,
            reason="snapshot",
            create_snapshot=True,
            snapshot_label="Known good",
            snapshot_reason="manual",
        ).snapshot
        self.assertIsNotNone(known_good)
        for database_path in (
            self.session.device_network_db,
            self.session.info_collected_db,
        ):
            with closing(sqlite3.connect(database_path)) as database:
                database.execute("UPDATE state SET value = 'current state'")
                database.commit()
        (self.session.backup_directory / "current.txt").write_text(
            "current backup", encoding="utf-8"
        )

        with tempfile.TemporaryDirectory() as temporary:
            recovery = Path(temporary) / "recovery"
            self.service._stage_workspace(self.session, recovery)
            original_replace = snapshot_module.os.replace
            injected = False

            def fail_during_second_database(source, destination):
                nonlocal injected
                if (
                    not injected
                    and Path(source).name == "info_collected.db"
                    and Path(destination) == self.session.info_collected_db
                ):
                    injected = True
                    raise OSError("injected rollback replacement failure")
                return original_replace(source, destination)

            with patch.object(
                snapshot_module.os, "replace", side_effect=fail_during_second_database
            ):
                with self.assertRaises(OSError):
                    self.service.snapshot_service.restore_snapshot(
                        self.session,
                        known_good.snapshot_id,
                        recovery_workspace=recovery,
                    )

        for database_path in (
            self.session.device_network_db,
            self.session.info_collected_db,
        ):
            with closing(sqlite3.connect(database_path)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM state").fetchone(),
                    ("current state",),
                )
        self.assertEqual(
            (self.session.backup_directory / "current.txt").read_text(encoding="utf-8"),
            "current backup",
        )
        self.assertFalse(
            any(path.name.startswith(".rollback-") for path in self.session.working_directory.iterdir())
        )


class _SlowWorkspaceService(WorkspaceService):
    def __init__(self, codec: WorkspacePackageCodec) -> None:
        super().__init__(codec, database_initializer=_initialize_test_databases)
        self.save_calls = 0
        self.active_saves = 0
        self.maximum_active_saves = 0

    def save_project(self, *args, **kwargs):
        self.save_calls += 1
        self.active_saves += 1
        self.maximum_active_saves = max(
            self.maximum_active_saves, self.active_saves
        )
        try:
            time.sleep(0.15)
            return super().save_project(*args, **kwargs)
        finally:
            self.active_saves -= 1


class WorkspaceSaveControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        codec = WorkspacePackageCodec(
            encryption_parameters=Argon2Parameters(
                memory_cost_kib=8 * 1024, iterations=1, lanes=1
            )
        )
        self.service = _SlowWorkspaceService(codec)
        self.welcome = WelcomeController(
            workspace_service=self.service,
            default_project_directory=self.temporary.name,
            recent_project_repository=RecentProjectRepository(
                Path(self.temporary.name) / "app_state.db"
            ),
        )
        self.controller = WorkspaceSaveController(
            self.welcome,
            workspace_service=self.service,
            autosave_interval_ms=60_000,
        )
        self.welcome.createProject("Background Save")
        self.app.processEvents()

    def tearDown(self) -> None:
        self.controller.shutdown()
        self.welcome.shutdown()
        self.temporary.cleanup()

    def test_manual_save_returns_immediately_and_runs_outside_qml_thread(self) -> None:
        completed = QSignalSpy(self.controller.saveCompleted)
        started_at = time.perf_counter()

        accepted = self.controller.requestManualSave()
        elapsed = time.perf_counter() - started_at

        self.assertTrue(accepted)
        self.assertLess(elapsed, 0.08)
        self.assertTrue(self.controller.busy)
        self.assertTrue(completed.wait(5_000))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.controller.state, "saved")

    def test_default_interval_is_three_minutes_and_menu_uses_standard_save_key(self) -> None:
        secondary_welcome = WelcomeController(
            workspace_service=self.service,
            default_project_directory=self.temporary.name,
            recent_project_repository=RecentProjectRepository(
                Path(self.temporary.name) / "secondary_app_state.db"
            ),
        )
        default_controller = WorkspaceSaveController(
            secondary_welcome, workspace_service=self.service
        )
        try:
            self.assertEqual(default_controller._autosave_timer.interval(), 180_000)
            self.assertEqual(default_controller._idle_autosave_timer.interval(), 5_000)
            self.assertTrue(default_controller._idle_autosave_timer.isSingleShot())
            menu_source = (
                Path(__file__).resolve().parents[1]
                / "UI/qml/app/WorkspaceMenuBar.qml"
            ).read_text(encoding="utf-8")
            main_source = (
                Path(__file__).resolve().parents[1] / "UI/qml/app/Main.qml"
            ).read_text(encoding="utf-8")
            self.assertIn("shortcut: StandardKey.Save", menu_source)
            self.assertIn("workspaceBackend.requestManualSave()", main_source)
        finally:
            default_controller.shutdown()
            secondary_welcome.shutdown()

    def test_repeated_manual_saves_are_coalesced_and_serialized(self) -> None:
        completed = QSignalSpy(self.controller.saveCompleted)

        self.controller.requestManualSave()
        self.controller.requestManualSave()
        self.controller.requestManualSave()

        self.assertTrue(completed.wait(5_000))
        if len(completed) < 2:
            self.assertTrue(completed.wait(5_000))
        self.assertEqual(self.service.save_calls, 2)
        self.assertEqual(self.service.maximum_active_saves, 1)

    def test_worker_is_owned_until_queued_completion_is_processed(self) -> None:
        completed = QSignalSpy(self.controller.saveCompleted)

        self.assertTrue(self.controller.requestManualSave())
        self.assertEqual(len(self.controller._workers), 1)
        self.assertTrue(completed.wait(5_000))

        self.assertEqual(self.controller._workers, {})

    def test_autosave_timer_runs_in_background_and_adds_history_when_dirty(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        with closing(sqlite3.connect(session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'timer change'")
            database.commit()
        self.controller.markDirty()
        self.controller._autosave_timer.setInterval(50)
        completed = QSignalSpy(self.controller.saveCompleted)

        self.assertTrue(completed.wait(5_000))

        self.assertGreaterEqual(self.service.save_calls, 1)
        self.assertGreaterEqual(len(self.controller.snapshots), 1)
        self.assertEqual(self.controller.snapshots[0]["reason"], "automatic")

    def test_dirty_burst_is_debounced_into_one_idle_autosave(self) -> None:
        self.controller._idle_autosave_timer.setInterval(40)
        completed = QSignalSpy(self.controller.saveCompleted)
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        with closing(sqlite3.connect(session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'debounced change'")
            database.commit()

        self.controller.markDirty()
        self.controller.markDirty()
        self.controller.markDirty()

        self.assertTrue(completed.wait(5_000))
        self.assertEqual(self.service.save_calls, 1)
        self.assertEqual(self.service.maximum_active_saves, 1)

    def test_closing_workspace_defers_temp_cleanup_until_worker_finishes(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        working_directory = session.working_directory

        self.controller.requestManualSave()
        self.welcome.closeProject()

        self.assertTrue(working_directory.exists())
        self.controller.shutdown()
        self.assertFalse(working_directory.exists())

    def test_menu_close_saves_dirty_state_before_releasing_temp_workspace(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        project = session.project_path
        working_directory = session.working_directory
        with closing(sqlite3.connect(session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'saved on close'")
            database.commit()
        self.controller.markDirty()
        closed = QSignalSpy(self.controller.workspaceCloseCompleted)

        self.assertTrue(self.controller.requestCloseWorkspace())
        self.assertTrue(closed.wait(5_000))

        self.assertIsNone(self.welcome.active_session())
        self.assertFalse(working_directory.exists())
        with self.service.open_project(project) as reopened:
            with closing(sqlite3.connect(reopened.device_network_db)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM state").fetchone(),
                    ("saved on close",),
                )

    def test_close_releases_database_users_before_removing_temp_workspace(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        working_directory = session.working_directory
        observed: list[tuple[bool, bool]] = []
        self.welcome.activeWorkspaceChanged.connect(
            lambda: observed.append(
                (self.welcome.active_session() is None, working_directory.exists())
            )
        )

        self.assertTrue(self.welcome.closeProject())

        self.assertEqual(observed, [(True, True)])
        self.assertFalse(working_directory.exists())

    def test_close_retries_transient_temp_directory_sharing_failure(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        working_directory = session.working_directory
        real_cleanup = session._temporary_directory.cleanup
        attempts = 0

        def flaky_cleanup():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise PermissionError("simulated sharing violation")
            real_cleanup()

        with patch.object(
            session._temporary_directory, "cleanup", side_effect=flaky_cleanup
        ):
            self.assertTrue(self.welcome.closeProject())

        self.assertEqual(attempts, 2)
        self.assertFalse(working_directory.exists())

    def test_shutdown_saves_then_removes_the_extracted_workspace(self) -> None:
        session = self.welcome.active_session()
        self.assertIsNotNone(session)
        project = session.project_path
        working_directory = session.working_directory
        with closing(sqlite3.connect(session.device_network_db)) as database:
            database.execute("UPDATE state SET value = 'saved at shutdown'")
            database.commit()

        self.controller.shutdown()

        self.assertIsNone(self.welcome.active_session())
        self.assertFalse(working_directory.exists())
        with self.service.open_project(project) as reopened:
            with closing(sqlite3.connect(reopened.device_network_db)) as database:
                self.assertEqual(
                    database.execute("SELECT value FROM state").fetchone(),
                    ("saved at shutdown",),
                )

    def test_close_disconnects_then_repacks_then_releases_workspace(self) -> None:
        events: list[str] = []
        original_save = self.service.save_project

        def prepare_close() -> None:
            events.append("disconnect")

        def save_with_event(*args, **kwargs):
            events.append("pack")
            self.assertTrue(kwargs["force"])
            return original_save(*args, **kwargs)

        controller = WorkspaceSaveController(
            self.welcome,
            workspace_service=self.service,
            autosave_interval_ms=60_000,
            workspace_close_preparer=prepare_close,
        )
        closed = QSignalSpy(controller.workspaceCloseCompleted)
        controller.workspaceCloseCompleted.connect(lambda: events.append("close"))
        try:
            with patch.object(self.service, "save_project", side_effect=save_with_event):
                self.assertTrue(controller.requestCloseWorkspace())
                self.assertTrue(closed.wait(5_000))
            self.assertEqual(events, ["disconnect", "pack", "close"])
        finally:
            controller.shutdown()


if __name__ == "__main__":
    unittest.main()
