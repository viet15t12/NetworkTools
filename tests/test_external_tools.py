from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from core.app_paths import APP_DIR
from core.external_tools import ExternalToolsManager
from core.tool_catalog import EXTERNAL_TOOL_CATALOG


class ExternalToolsManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.manager = ExternalToolsManager(
            db_path=self.root / "external_tools.db",
            device_db_path=self.root / "device_network.db",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _executable(self, name: str = "tool.exe") -> Path:
        path = self.root / name
        path.write_bytes(b"MZ")
        return path

    def test_validate_executable_normalizes_file_urls_and_rejects_invalid_paths(self) -> None:
        executable = self._executable("Detected Tool.exe")

        with patch("core.external_tools.sys.platform", "win32"):
            valid = self.manager.validateExecutable(executable.as_uri())
            invalid_extension = self.manager.validateExecutable(str(self._executable("notes.txt")))
            missing = self.manager.validateExecutable(str(self.root / "missing.exe"))

        self.assertTrue(valid["ok"])
        self.assertEqual(Path(valid["path"]), executable)
        self.assertFalse(invalid_extension["ok"])
        self.assertIn("Windows executable", invalid_extension["message"])
        self.assertFalse(missing["ok"])
        self.assertFalse(missing["exists"])

    def test_save_blocks_password_placeholders_and_persists_valid_tools(self) -> None:
        executable = self._executable("putty.exe")

        blocked = self.manager.saveTool(
            "Unsafe PuTTY",
            "SSH Client",
            str(executable),
            "-ssh {ip} -pw {password}",
            True,
            "Must not be saved",
        )
        saved = self.manager.saveTool(
            "PuTTY",
            "SSH Client",
            str(executable),
            "-ssh {ip}",
            True,
            "Detected SSH client",
        )

        self.assertFalse(blocked["ok"])
        self.assertIn("blocked", blocked["message"])
        self.assertTrue(saved["ok"])
        self.assertEqual([tool["app"] for tool in self.manager.getTools()], ["PuTTY"])

    def test_discovery_merges_default_associations_and_marks_saved_candidates(self) -> None:
        executable = self._executable("putty.exe")

        def installed_paths(spec):
            if spec["app"] == "PuTTY":
                return [(str(executable), "Windows App Paths", "High")]
            return []

        defaults = [
            {
                "executable": str(executable),
                "association": "ssh",
                "explicit": True,
                "type": "SSH Client",
            }
        ]

        with (
            patch("core.external_tools.sys.platform", "win32"),
            patch.object(self.manager, "_installed_paths_for_spec", side_effect=installed_paths),
            patch.object(self.manager, "_windows_default_handlers", return_value=defaults),
        ):
            first_scan = self.manager.discoverWindowsTools()
            self.manager.saveTool("PuTTY", "SSH Client", str(executable), "-ssh {ip}", True, "")
            second_scan = self.manager.discoverWindowsTools()

        self.assertEqual(len(first_scan), 1)
        self.assertTrue(first_scan[0]["isDefault"])
        self.assertTrue(first_scan[0]["explicitDefault"])
        self.assertEqual(first_scan[0]["defaultFor"], ["ssh"])
        self.assertEqual(first_scan[0]["source"], "Windows default association")
        self.assertFalse(first_scan[0]["alreadyConfigured"])
        self.assertTrue(second_scan[0]["alreadyConfigured"])

    def test_xshell_is_detected_with_safe_official_url_arguments(self) -> None:
        executable = self._executable("Xshell.exe")

        def installed_paths(spec):
            if spec["app"] == "Xshell":
                return [(str(executable), "Windows App Paths", "High")]
            return []

        with (
            patch("core.external_tools.sys.platform", "win32"),
            patch.object(self.manager, "_installed_paths_for_spec", side_effect=installed_paths),
            patch.object(self.manager, "_windows_default_handlers", return_value=[]),
        ):
            candidates = self.manager.discoverWindowsTools()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["app"], "Xshell")
        self.assertEqual(candidates[0]["type"], "SSH Client")
        self.assertEqual(candidates[0]["arguments"], "-url ssh://{ip}")
        self.assertEqual(candidates[0]["source"], "Windows App Paths")

    def test_installed_app_registry_path_participates_in_discovery(self) -> None:
        executable = self._executable("MobaXterm.exe")
        target_spec = next(
            spec for spec in self.manager.WINDOWS_TOOL_SPECS
            if spec["app"] == "MobaXterm"
        )

        with (
            patch.object(self.manager, "_windows_app_path", return_value=""),
            patch("core.external_tools.shutil.which", return_value=None),
            patch.object(
                self.manager,
                "_windows_uninstall_paths",
                return_value=[str(executable)],
            ),
        ):
            paths = self.manager._installed_paths_for_spec(target_spec)

        self.assertEqual(
            paths,
            [(str(executable), "Windows installed applications", "High")],
        )

    def test_official_default_terminal_guids_resolve_expected_applications(self) -> None:
        terminal = self._executable("wt.exe")
        console_host = self._executable("cmd.exe")
        scenarios = (
            (self.manager.DEFAULT_TERMINAL_AUTOMATIC_GUID, terminal, False),
            (self.manager.DEFAULT_CONSOLE_HOST_GUID, console_host, True),
            (self.manager.DEFAULT_WINDOWS_TERMINAL_GUID, terminal, True),
            (self.manager.DEFAULT_WINDOWS_TERMINAL_PREVIEW_GUID, terminal, True),
        )

        for delegation_guid, expected_path, expected_explicit in scenarios:
            with self.subTest(delegation_guid=delegation_guid):
                def registry_value(_root, _key_path, value_name=None):
                    if value_name == "DelegationTerminal":
                        return delegation_guid
                    return ""

                def which(executable_name):
                    if executable_name.casefold() == "cmd.exe":
                        return str(console_host)
                    if executable_name.casefold() == "wt.exe":
                        return str(terminal)
                    return None

                with (
                    patch("core.external_tools.sys.platform", "win32"),
                    patch("core.external_tools.shutil.which", side_effect=which),
                    patch.object(self.manager, "_windows_registry_value", side_effect=registry_value),
                    patch.object(self.manager, "_windows_app_path", return_value=str(terminal)),
                ):
                    handlers = self.manager._windows_default_handlers()

                terminal_handlers = [row for row in handlers if row["association"] == "Default terminal"]
                self.assertEqual(len(terminal_handlers), 1)
                self.assertEqual(Path(terminal_handlers[0]["executable"]), expected_path)
                self.assertEqual(terminal_handlers[0]["explicit"], expected_explicit)

    def test_windows_defaults_include_ssh_telnet_and_sftp_protocols(self) -> None:
        executable = self._executable("Xshell.exe")
        sftp_executable = self._executable("WinSCP.exe")
        requested: list[tuple[str, bool]] = []

        def association_handler(association: str, protocol: bool):
            requested.append((association, protocol))
            if association == "telnet":
                return {
                    "executable": str(executable),
                    "association": association,
                    "explicit": True,
                    "progId": "Xshell.telnet",
                }
            if association == "sftp":
                return {
                    "executable": str(sftp_executable),
                    "association": association,
                    "explicit": True,
                    "progId": "WinSCP.sftp",
                }
            return None

        with (
            patch("core.external_tools.sys.platform", "win32"),
            patch.object(self.manager, "_windows_association_handler", side_effect=association_handler),
            patch.object(self.manager, "_windows_registry_value", return_value=""),
            patch.object(self.manager, "_windows_app_path", return_value=""),
            patch("core.external_tools.shutil.which", return_value=None),
        ):
            handlers = self.manager._windows_default_handlers()

        self.assertIn(("ssh", True), requested)
        self.assertIn(("telnet", True), requested)
        self.assertIn(("sftp", True), requested)
        telnet = next(row for row in handlers if row["association"] == "telnet")
        self.assertEqual(telnet["type"], "SSH Client")
        self.assertTrue(telnet["explicit"])
        sftp = next(row for row in handlers if row["association"] == "sftp")
        self.assertEqual(sftp["type"], "SFTP Client")
        self.assertTrue(sftp["explicit"])

    def test_sftp_is_an_optional_external_application_type(self) -> None:
        self.assertIn("SFTP Client", self.manager.TOOL_TYPES)
        winscp = next(
            spec for spec in self.manager.WINDOWS_TOOL_SPECS
            if spec["app"] == "WinSCP"
        )
        self.assertEqual(winscp["type"], "SFTP Client")
        self.assertIn("{ip}", winscp["arguments"])
        self.assertIn("{username}", winscp["arguments"])

    def test_activity_launches_enabled_sftp_client_without_target_placeholders(self) -> None:
        executable = self._executable("WinSCP.exe")
        saved = self.manager.saveTool(
            "WinSCP",
            "SFTP Client",
            str(executable),
            "/ini=nul sftp://{username}@{ip}:{port}{path}",
            True,
            "Preferred SFTP client",
        )
        self.assertTrue(saved["ok"])
        self.assertTrue(self.manager.hasEnabledSftpClient)

        with patch("core.external_tools.subprocess.Popen") as popen:
            result = self.manager.openSftpClient("", 22, "", "/")

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "external")
        popen.assert_called_once_with(
            [str(executable), "/ini=nul"],
            cwd=str(APP_DIR),
        )

    def test_sftp_launcher_substitutes_target_without_passing_password(self) -> None:
        executable = self._executable("WinSCP.exe")
        saved = self.manager.saveTool(
            "WinSCP",
            "SFTP Client",
            str(executable),
            "sftp://{username}@{ip}:{port}{path}",
            True,
            "Preferred SFTP client",
        )
        self.assertTrue(saved["ok"])

        with patch("core.external_tools.subprocess.Popen") as popen:
            result = self.manager.openSftpClient(
                "192.0.2.40",
                2222,
                "network-admin",
                "/configs",
            )

        self.assertTrue(result["ok"])
        popen.assert_called_once_with(
            [
                str(executable),
                "sftp://network-admin@192.0.2.40:2222/configs",
            ],
            cwd=str(APP_DIR),
        )
        self.assertNotIn("password", str(popen.call_args).casefold())

    def test_sftp_launcher_falls_back_to_builtin_and_blocks_legacy_password(self) -> None:
        no_tool = self.manager.openSftpClient("", 22, "", "/")
        self.assertTrue(no_tool["ok"])
        self.assertEqual(no_tool["mode"], "builtin")

        executable = self._executable("legacy-sftp.exe")
        with closing(sqlite3.connect(self.manager.db_path)) as connection:
            connection.execute(
                """
                INSERT INTO apps (app, type, executable, arguments, enabled, description)
                VALUES (?, ?, ?, ?, 1, '');
                """,
                (
                    "Legacy SFTP",
                    "SFTP Client",
                    str(executable),
                    "-password={password} sftp://{ip}/",
                ),
            )
            connection.commit()

        with patch("core.external_tools.subprocess.Popen") as popen:
            blocked = self.manager.openSftpClient("192.0.2.41", 22, "admin", "/")

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["mode"], "builtin")
        self.assertIn("blocked", blocked["message"].casefold())
        self.assertEqual(blocked["settingsKey"], "external_tools")
        popen.assert_not_called()

    def test_terminal_suggestions_are_hosts_not_powershell_shells(self) -> None:
        terminal_apps = {
            spec["app"]
            for spec in self.manager.WINDOWS_TOOL_SPECS
            if spec["type"] == "Terminal"
        }
        self.assertEqual(terminal_apps, {"Windows Terminal", "Command Prompt"})

    def test_terminal_alias_and_package_path_are_one_application_choice(self) -> None:
        alias = self._executable("wt.exe")
        package_root = self.root / "WindowsApps" / "Terminal"
        package_root.mkdir(parents=True)
        package = package_root / "wt.exe"
        package.write_bytes(b"MZ")

        def installed_paths(spec):
            if spec["app"] == "Windows Terminal":
                return [(str(alias), "PATH / App Execution Alias", "Medium")]
            return []

        defaults = [{
            "executable": str(package),
            "association": "Default terminal",
            "explicit": True,
            "type": "Terminal",
        }]
        with (
            patch("core.external_tools.sys.platform", "win32"),
            patch.object(self.manager, "_installed_paths_for_spec", side_effect=installed_paths),
            patch.object(self.manager, "_windows_default_handlers", return_value=defaults),
        ):
            candidates = self.manager.discoverExternalTools()

        terminals = [row for row in candidates if row["app"] == "Windows Terminal"]
        self.assertEqual(len(terminals), 1)
        self.assertEqual(Path(terminals[0]["executable"]), package)
        self.assertTrue(terminals[0]["isDefault"])
        self.assertFalse(terminals[0]["isAmbiguous"])

    def test_saving_an_active_tool_disables_the_previous_app_in_category(self) -> None:
        putty = self._executable("putty.exe")
        xshell = self._executable("Xshell.exe")

        self.assertTrue(self.manager.saveTool(
            "PuTTY", "SSH Client", str(putty), "-ssh {ip}", True, ""
        )["ok"])
        self.assertTrue(self.manager.saveTool(
            "Xshell", "SSH Client", str(xshell), "-url ssh://{ip}", True, ""
        )["ok"])

        by_name = {tool["app"]: tool for tool in self.manager.getTools()}
        self.assertEqual(by_name["PuTTY"]["enabled"], 0)
        self.assertEqual(by_name["Xshell"]["enabled"], 1)

    def test_linux_discovery_prioritizes_desktop_default_over_suggestion(self) -> None:
        executable = self._executable("remmina")

        def installed_paths(spec):
            if spec["app"] == "Remmina":
                return [(str(executable), "PATH", "High")]
            return []

        defaults = [{
            "executable": str(executable),
            "association": "telnet",
            "explicit": True,
            "type": "SSH Client",
            "app": "Remmina",
        }]
        with (
            patch("core.external_tools.sys.platform", "linux"),
            patch.object(self.manager, "_installed_paths_for_spec", side_effect=installed_paths),
            patch.object(self.manager, "_linux_default_handlers", return_value=defaults),
            patch.object(self.manager, "_linux_desktop_specs", return_value=[]),
        ):
            candidates = self.manager.discoverExternalTools()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["app"], "Remmina")
        self.assertTrue(candidates[0]["isDefault"])
        self.assertEqual(candidates[0]["source"], "Linux default application")
        self.assertEqual(candidates[0]["defaultFor"], ["telnet"])

    def test_linux_discovers_terminal_from_xdg_desktop_entry(self) -> None:
        data_home = self.root / "share"
        applications = data_home / "applications"
        applications.mkdir(parents=True)
        executable = self._executable("ptyxis")
        (applications / "org.gnome.Ptyxis.desktop").write_text(
            "\n".join((
                "[Desktop Entry]",
                "Type=Application",
                "Name=Ptyxis",
                f"Exec={executable} %U",
                "Comment=Container-oriented terminal",
                "Categories=GNOME;System;TerminalEmulator;",
            )),
            encoding="utf-8",
        )

        with (
            patch("core.external_tools.sys.platform", "linux"),
            patch.object(
                self.manager,
                "_linux_application_dirs",
                return_value=[applications],
            ),
            patch.object(self.manager, "_installed_paths_for_spec", return_value=[]),
            patch.object(self.manager, "_linux_default_handlers", return_value=[]),
        ):
            candidates = self.manager.discoverExternalTools()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["app"], "Ptyxis")
        self.assertEqual(candidates[0]["type"], "Terminal")
        self.assertEqual(candidates[0]["executable"], str(executable))
        self.assertEqual(candidates[0]["arguments"], "")
        self.assertEqual(candidates[0]["source"], "Linux desktop application")

    def test_linux_desktop_scan_ignores_unrelated_apps(self) -> None:
        data_home = self.root / "share"
        applications = data_home / "applications"
        applications.mkdir(parents=True)
        executable = self._executable("calculator")
        (applications / "calculator.desktop").write_text(
            "\n".join((
                "[Desktop Entry]",
                "Type=Application",
                "Name=Calculator",
                f"Exec={executable}",
                "Categories=Utility;Calculator;",
            )),
            encoding="utf-8",
        )

        with (
            patch("core.external_tools.sys.platform", "linux"),
            patch.object(
                self.manager,
                "_linux_application_dirs",
                return_value=[applications],
            ),
            patch.object(self.manager, "_installed_paths_for_spec", return_value=[]),
            patch.object(self.manager, "_linux_default_handlers", return_value=[]),
        ):
            candidates = self.manager.discoverExternalTools()

        self.assertEqual(candidates, [])

    def test_linux_flatpak_desktop_entries_keep_runner_arguments(self) -> None:
        data_home = self.root / "share"
        applications = data_home / "applications"
        applications.mkdir(parents=True)
        flatpak = self._executable("flatpak")
        (applications / "org.example.Terminal.desktop").write_text(
            "\n".join((
                "[Desktop Entry]",
                "Type=Application",
                "Name=Example Terminal",
                f"Exec={flatpak} run org.example.Terminal %U",
                "Categories=System;TerminalEmulator;",
            )),
            encoding="utf-8",
        )

        with (
            patch("core.external_tools.sys.platform", "linux"),
            patch.object(
                self.manager,
                "_linux_application_dirs",
                return_value=[applications],
            ),
            patch.object(self.manager, "_installed_paths_for_spec", return_value=[]),
            patch.object(self.manager, "_linux_default_handlers", return_value=[]),
        ):
            candidates = self.manager.discoverExternalTools()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["app"], "Example Terminal")
        self.assertEqual(
            candidates[0]["arguments"],
            "run org.example.Terminal",
        )

    def test_linux_desktop_entry_unwraps_env_launcher(self) -> None:
        data_home = self.root / "share"
        applications = data_home / "applications"
        applications.mkdir(parents=True)
        executable = self._executable("snap-terminal")
        (applications / "snap-terminal.desktop").write_text(
            "\n".join((
                "[Desktop Entry]",
                "Type=Application",
                "Name=Snap Terminal",
                f"Exec=/usr/bin/env DESKTOP_HINT=1 {executable} %U",
                "Categories=System;TerminalEmulator;",
            )),
            encoding="utf-8",
        )

        with (
            patch("core.external_tools.sys.platform", "linux"),
            patch.object(
                self.manager,
                "_linux_application_dirs",
                return_value=[applications],
            ),
            patch.object(self.manager, "_installed_paths_for_spec", return_value=[]),
            patch.object(self.manager, "_linux_default_handlers", return_value=[]),
        ):
            candidates = self.manager.discoverExternalTools()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["executable"], str(executable))
        self.assertEqual(candidates[0]["arguments"], "")

    def test_launch_refuses_legacy_password_arguments_before_process_creation(self) -> None:
        executable = self._executable("legacy.exe")
        with closing(sqlite3.connect(self.manager.db_path)) as connection:
            connection.execute(
                """
                INSERT INTO apps (app, type, executable, arguments, enabled, description)
                VALUES (?, ?, ?, ?, 1, '');
                """,
                ("Legacy", "SSH Client", str(executable), "-pw {password} {ip}"),
            )
            connection.commit()

        with patch("core.external_tools.subprocess.Popen") as popen:
            result = self.manager.openDeviceCli("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertIn("blocked", result["message"])
        self.assertEqual(result["settingsKey"], "external_tools")
        popen.assert_not_called()

    def test_missing_ssh_client_identifies_the_external_tools_settings(self) -> None:
        result = self.manager.openDeviceCli("192.0.2.10")

        self.assertFalse(result["ok"])
        self.assertEqual(result["settingsKey"], "external_tools")

    def test_launches_enabled_xshell_for_selected_device(self) -> None:
        executable = self._executable("Xshell.exe")
        saved = self.manager.saveTool(
            "Xshell",
            "SSH Client",
            str(executable),
            "-url ssh://{ip}",
            True,
            "Preferred SSH client",
        )
        self.assertTrue(saved["ok"])

        with patch("core.external_tools.subprocess.Popen") as popen:
            result = self.manager.openDeviceCli("192.0.2.25")

        self.assertTrue(result["ok"])
        self.assertIn("Xshell", result["message"])
        popen.assert_called_once_with(
            [str(executable), "-url", "ssh://192.0.2.25"],
            cwd=str(APP_DIR),
        )

    def test_catalog_is_an_https_allowlist_and_never_runs_an_installer(self) -> None:
        self.assertGreaterEqual(len(EXTERNAL_TOOL_CATALOG), 8)
        self.assertTrue(
            all(
                str(entry["officialUrl"]).startswith("https://")
                for entry in EXTERNAL_TOOL_CATALOG
            )
        )

        with (
            patch.object(
                self.manager,
                "_installed_paths_for_spec",
                return_value=[],
            ),
            patch("core.external_tools.subprocess.run") as run,
            patch("core.external_tools.subprocess.Popen") as popen,
        ):
            catalog = self.manager.getExternalToolCatalog()

        self.assertTrue(catalog)
        self.assertTrue(all(row["status"] == "Not installed" for row in catalog))
        run.assert_not_called()
        popen.assert_not_called()

    def test_catalog_includes_letos_as_a_database_browser(self) -> None:
        letos = next(
            entry for entry in EXTERNAL_TOOL_CATALOG
            if entry["app"] == "Letos"
        )
        self.assertEqual(letos["category"], "DB Browser")
        self.assertEqual(letos["officialUrl"], "https://letos.org/")

    def test_catalog_does_not_mark_a_missing_saved_executable_as_ready(self) -> None:
        with closing(sqlite3.connect(self.manager.db_path)) as connection:
            connection.execute(
                """
                INSERT INTO apps (
                    app, type, executable, arguments, enabled, description
                )
                VALUES ('PuTTY', 'SSH Client', ?, '-ssh {ip}', 1, '');
                """,
                (str(self.root / "missing-putty.exe"),),
            )
            connection.commit()

        with patch.object(
            self.manager,
            "_installed_paths_for_spec",
            return_value=[],
        ):
            catalog = self.manager.getExternalToolCatalog()

        putty = next(row for row in catalog if row["app"] == "PuTTY")
        self.assertTrue(putty["saved"])
        self.assertFalse(putty["installed"])
        self.assertFalse(putty["configured"])
        self.assertFalse(putty["enabled"])
        self.assertEqual(putty["status"], "Configured path missing")

    def test_catalog_reports_the_active_application_for_its_category(self) -> None:
        executable = self._executable("putty.exe")
        self.assertTrue(self.manager.saveTool(
            "PuTTY", "SSH Client", str(executable), "-ssh {ip}", True, ""
        )["ok"])

        def installed_paths(spec):
            if spec["app"] == "PuTTY":
                return [(str(executable), "Windows App Paths", "High")]
            return []

        with patch.object(
            self.manager,
            "_installed_paths_for_spec",
            side_effect=installed_paths,
        ):
            catalog = self.manager.getExternalToolCatalog()

        putty = next(row for row in catalog if row["app"] == "PuTTY")
        self.assertTrue(putty["installed"])
        self.assertTrue(putty["configured"])
        self.assertTrue(putty["enabled"])
        self.assertEqual(putty["status"], "Configured")


if __name__ == "__main__":
    unittest.main()
