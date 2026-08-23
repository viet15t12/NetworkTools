from __future__ import annotations

import unittest
import tempfile
from contextlib import closing
from pathlib import Path

from PyQt6.QtCore import QUrl

from core.welcome import WelcomeController
from infrastructure.database.recent_projects import RecentProjectRepository
from infrastructure.workspace import Argon2Parameters, WorkspacePackageCodec, WorkspaceService


class WelcomeControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        codec = WorkspacePackageCodec(
            encryption_parameters=Argon2Parameters(
                memory_cost_kib=8 * 1024, iterations=1, lanes=1
            )
        )
        self.controller = WelcomeController(
            workspace_service=WorkspaceService(codec),
            default_project_directory=self.temporary.name,
            recent_project_repository=RecentProjectRepository(
                Path(self.temporary.name) / "app_state.db"
            ),
        )
        self.workspace_requests: list[tuple[str, str]] = []
        self.welcome_requests: list[str] = []
        self.password_requests: list[str] = []
        self.controller.workspaceRequested.connect(
            lambda name, path: self.workspace_requests.append((name, path))
        )
        self.controller.welcomeRequested.connect(self.welcome_requests.append)
        self.controller.passwordRequired.connect(self.password_requests.append)

    def tearDown(self) -> None:
        self.controller.shutdown()
        self.temporary.cleanup()

    def test_no_demo_projects_are_suggested_without_real_recents(self) -> None:
        projects = self.controller.recentProjects

        self.assertEqual(projects, [])
        self.assertEqual(self.workspace_requests, [])

        self.controller.openRecent("does-not-exist")

        self.assertEqual(self.workspace_requests, [])

    def test_recent_projects_only_list_real_existing_workspaces(self) -> None:
        self.controller.createProject("Campus Core / Lab")

        projects = self.controller.recentProjects

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Campus Core / Lab")
        self.assertTrue(Path(str(projects[0]["path"])).is_file())

    def test_create_project_builds_real_ntp_and_active_temp_workspace(self) -> None:
        self.controller.createProject("Campus Core / Lab")

        name, path = self.workspace_requests[0]
        self.assertEqual(name, "Campus Core / Lab")
        self.assertTrue(path.endswith("Campus-Core-Lab.ntp"))
        self.assertTrue(Path(path).is_file())
        self.assertTrue(Path(self.controller.activeWorkspacePath).is_dir())

    def test_create_project_at_uses_selected_location_and_adds_extension(self) -> None:
        selected = Path(self.temporary.name) / "chosen" / "Custom Name"
        selected.parent.mkdir()

        self.controller.createProjectAt(
            "Custom Name", QUrl.fromLocalFile(str(selected)), ""
        )

        _, created_path = self.workspace_requests[-1]
        self.assertEqual(Path(created_path), selected.with_suffix(".ntp"))
        self.assertTrue(Path(created_path).is_file())

    def test_create_project_in_uses_selected_folder_and_generated_file_name(self) -> None:
        selected_folder = Path(self.temporary.name) / "selected folder"
        selected_folder.mkdir()

        self.controller.createProjectIn(
            "Campus Core / Lab",
            QUrl.fromLocalFile(str(selected_folder)),
            "",
        )

        _, created_path = self.workspace_requests[-1]
        self.assertEqual(
            Path(created_path), selected_folder / "Campus-Core-Lab.ntp"
        )
        self.assertTrue(Path(created_path).is_file())

    def test_open_project_uses_selected_file_name(self) -> None:
        self.controller.createProject("Edge-Lab")
        project_path = self.workspace_requests[-1][1]
        self.workspace_requests.clear()
        self.controller.openProject(QUrl.fromLocalFile(project_path))

        self.assertEqual(self.workspace_requests[0][0], "Edge-Lab")
        self.assertTrue(self.workspace_requests[0][1].endswith("Edge-Lab.ntp"))

    def test_encrypted_project_requests_password_then_unlocks(self) -> None:
        self.controller.createProject("Secret Lab", "correct password")
        project_path = self.workspace_requests[-1][1]
        self.workspace_requests.clear()

        self.controller.openProject(QUrl.fromLocalFile(project_path))

        self.assertEqual(self.password_requests, [project_path])
        self.assertEqual(self.workspace_requests, [])
        self.controller.unlockProject("correct password")
        self.assertEqual(self.workspace_requests[0][0], "Secret Lab")
        self.assertTrue(self.controller.activeProjectEncrypted)

    def test_welcome_mode_is_bounded_to_supported_actions(self) -> None:
        self.controller.requestWelcome("settings")
        self.controller.requestWelcome("unsupported")

        self.assertEqual(self.welcome_requests, ["settings", ""])

    def test_launcher_loads_welcome_before_workspace(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text(
            encoding="utf-8"
        )

        welcome_load = source.index('engine.loadFromModule("UI", "Welcome")')
        workspace_load = source.index('engine.loadFromModule("UI", "Main")')
        workspace_handler = source.index("def open_workspace(")

        self.assertGreater(workspace_load, workspace_handler)
        self.assertGreater(welcome_load, workspace_handler)
        self.assertIn(
            'context.setContextProperty("welcomeController", welcome_controller)',
            source,
        )
        self.assertNotIn('welcome_controller.openRecent(str(most_recent["id"]))', source)


    def test_persistent_recents_record_and_get_most_recent(self) -> None:
        self.controller.createProject("Persistent Lab")
        _, created_path = self.workspace_requests[-1]

        most_recent = self.controller.get_most_recent_project()
        self.assertIsNotNone(most_recent)
        self.assertEqual(most_recent["name"], "Persistent Lab")
        self.assertEqual(most_recent["path"], created_path)
        self.assertNotIn("isMock", most_recent)
        self.assertEqual(most_recent["url"], Path(created_path).resolve().as_uri())
        self.assertRegex(
            most_recent["openedAtDisplay"],
            r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$",
        )

        self.controller.removeRecent(created_path)
        new_most_recent = self.controller.get_most_recent_project()
        self.assertIsNone(new_most_recent)

    def test_recent_project_is_persisted_in_sqlite(self) -> None:
        self.controller.createProject("Database History")
        _, created_path = self.workspace_requests[-1]

        import sqlite3

        with closing(sqlite3.connect(Path(self.temporary.name) / "app_state.db")) as connection:
            row = connection.execute(
                """
                SELECT name, path, project_url, opened_at
                FROM recent_projects
                WHERE path = ?
                """,
                (created_path,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Database History")
        self.assertEqual(row[1], created_path)
        self.assertEqual(row[2], Path(created_path).resolve().as_uri())
        self.assertIn("T", row[3])


if __name__ == "__main__":
    unittest.main()
