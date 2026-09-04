from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class LauncherContractTests(unittest.TestCase):
    def test_linux_installer_creates_standalone_user_launcher(self) -> None:
        installer = (APP_ROOT / "install.sh").read_text(encoding="utf-8")
        launcher = (APP_ROOT / "packaging/linux/cams-launcher").read_text(
            encoding="utf-8"
        )

        self.assertIn("CAMS_INSTALL_SKIP_SETUP", installer)
        self.assertIn("cams.desktop", installer)
        self.assertIn('ln -sfn "$app_dir/cams-launcher"', installer)
        self.assertIn('exec "$python" "$app_dir/main.py"', launcher)
        self.assertIn("CAMS_DATA_DIR", launcher)
        self.assertIn("update.sh", installer)
        self.assertIn("CAMS_INSTALL_BASE", launcher)

    @unittest.skipIf(os.name == "nt", "POSIX updater test")
    def test_updater_checks_and_installs_a_new_git_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote = root / "remote"
            installed = root / "installed"
            install_base = root / "target"
            remote.mkdir()
            installed.mkdir()
            subprocess.run(
                ["git", "init", "-q", "-b", "main"], cwd=remote, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=remote,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "CAMS Test"],
                cwd=remote,
                check=True,
            )
            fake_installer = remote / "install.sh"
            fake_installer.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "mkdir -p \"$CAMS_INSTALL_BASE\"\n"
                "printf '%s\\n' \"$CAMS_UPDATE_COMMIT\" > \"$CAMS_INSTALL_BASE/installed-commit\"\n",
                encoding="utf-8",
            )
            fake_installer.chmod(0o755)
            (remote / "payload").write_text("first\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=remote, check=True)
            subprocess.run(["git", "commit", "-qm", "first"], cwd=remote, check=True)
            first_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=remote, check=True,
                text=True, capture_output=True,
            ).stdout.strip()

            shutil.copy2(APP_ROOT / "update.sh", installed / "update.sh")
            (installed / ".cams-release").write_text(
                f"{first_commit}\nmain\n{remote}\n", encoding="utf-8"
            )
            environment = os.environ.copy()
            environment["CAMS_INSTALL_BASE"] = str(install_base)

            current = subprocess.run(
                [str(installed / "update.sh"), "--check"],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
            self.assertIn("CAMS_UPDATE_STATUS=current", current.stdout)

            (remote / "payload").write_text("second\n", encoding="utf-8")
            subprocess.run(["git", "add", "payload"], cwd=remote, check=True)
            subprocess.run(["git", "commit", "-qm", "second"], cwd=remote, check=True)
            second_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=remote, check=True,
                text=True, capture_output=True,
            ).stdout.strip()

            available = subprocess.run(
                [str(installed / "update.sh"), "--check"],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(available.returncode, 0, available.stdout + available.stderr)
            self.assertIn("CAMS_UPDATE_STATUS=available", available.stdout)

            updated = subprocess.run(
                [str(installed / "update.sh"), "--update"],
                env=environment, text=True, capture_output=True, check=False,
            )
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            self.assertIn("CAMS_UPDATE_STATUS=updated", updated.stdout)
            self.assertEqual(
                (install_base / "installed-commit").read_text(encoding="utf-8").strip(),
                second_commit,
            )

    @unittest.skipIf(os.name == "nt", "POSIX installer test")
    def test_linux_install_update_and_uninstall_preserve_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            environment = os.environ.copy()
            environment.update({
                "HOME": str(root / "home"),
                "XDG_DATA_HOME": str(root / "share"),
                "CAMS_BIN_DIR": str(root / "bin"),
                "CAMS_INSTALL_SKIP_SETUP": "1",
            })
            (root / "home").mkdir()
            installer = APP_ROOT / "install.sh"
            uninstaller = APP_ROOT / "uninstall.sh"

            first = subprocess.run(
                [str(installer)], env=environment, text=True,
                capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue((root / "bin/cams").is_symlink())
            desktop_file = root / "share/applications/cams.desktop"
            self.assertTrue(desktop_file.is_file())
            desktop_entry = desktop_file.read_text(encoding="utf-8")
            scalable_icon = root / "share/icons/hicolor/scalable/apps/cams.svg"
            bitmap_icon = root / "share/icons/hicolor/256x256/apps/cams.png"
            self.assertIn(f"Icon={scalable_icon}", desktop_entry)
            self.assertTrue(scalable_icon.is_file())
            self.assertTrue(bitmap_icon.is_file())
            self.assertTrue((root / "share/cams/app/main.py").is_file())
            self.assertFalse((root / "share/cams/app/docs").exists())

            sentinel = root / "share/cams/data/preserved"
            sentinel.write_text("keep", encoding="utf-8")
            update = subprocess.run(
                [str(installer)], env=environment, text=True,
                capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

            removed = subprocess.run(
                [str(uninstaller)], env=environment, text=True,
                capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            self.assertFalse((root / "share/cams/app").exists())
            self.assertFalse(desktop_file.exists())
            self.assertFalse(scalable_icon.exists())
            self.assertFalse(bitmap_icon.exists())
            self.assertTrue(sentinel.is_file())

    @unittest.skipIf(os.name == "nt", "POSIX shell launcher test")
    def test_optional_setup_skips_native_build_without_python_headers(self) -> None:
        shell_path = APP_ROOT / "cams.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_uv = Path(temp_dir) / "uv"
            fake_uv.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  --version) echo 'uv-test 0.0'; exit 0 ;;\n"
                "  sync) exit 0 ;;\n"
                "  run)\n"
                "    case \"$*\" in\n"
                "      *Python.h*) exit 1 ;;\n"
                "      *'sync engine'*)\n"
                "        echo 'sync engine: _engine.py (Python fallback)'; exit 0 ;;\n"
                "    esac\n"
                "    ;;\n"
                "esac\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = temp_dir + os.pathsep + environment.get("PATH", "")
            completed = subprocess.run(
                ["sh", str(shell_path), "setup"],
                text=True,
                capture_output=True,
                cwd=APP_ROOT,
                env=environment,
                timeout=30,
                check=False,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        self.assertIn("Skipping optional Cython acceleration", output)
        self.assertIn("Python fallback", output)
        self.assertNotIn("Building optional Cython", output)

    def test_setup_treats_cython_acceleration_as_optional(self) -> None:
        batch = (APP_ROOT / "cams.bat").read_text(encoding="utf-8")
        shell = (APP_ROOT / "cams.sh").read_text(encoding="utf-8")

        self.assertIn('"%~f0" build', batch)
        self.assertIn("build_cython_optional", shell)
        self.assertIn("sync engine fallback", batch)
        self.assertIn("sync engine fallback", shell)
        self.assertIn("has_python_headers", shell)
        self.assertIn("Skipping optional Cython acceleration", shell)

    def test_explicit_build_stays_strict(self) -> None:
        batch = (APP_ROOT / "cams.bat").read_text(encoding="utf-8")
        shell = (APP_ROOT / "cams.sh").read_text(encoding="utf-8")

        self.assertIn('if /I "%~1"=="build" goto build', batch)
        self.assertIn("build) build_cython ;;", shell)
        self.assertIn("require_python_headers", shell)

    def test_setup_checks_optional_terminal_companion(self) -> None:
        shell = (APP_ROOT / "cams.sh").read_text(encoding="utf-8")

        self.assertIn("check_terminal_optional", shell)
        self.assertIn("build_terminal_optional", shell)
        self.assertIn("terminal-check) check_terminal", shell)
        self.assertIn("terminal-build) build_terminal", shell)
        self.assertIn("CAMS_TERMINAL_BINARY", shell)
        self.assertIn("--bin cams-terminal", shell)
        self.assertIn("prepare_environment", shell)
        self.assertIn("unset VIRTUAL_ENV", shell)
        self.assertIn('/.cargo}/env"', shell)

    def test_run_checks_cpp_and_rust_binaries_before_starting_python(self) -> None:
        shell = (APP_ROOT / "cams.sh").read_text(encoding="utf-8")

        self.assertIn("ensure_runtime_binaries", shell)
        self.assertIn("ensure_syslog_collector", shell)
        self.assertIn("ensure_terminal", shell)
        self.assertIn("syslog_sources_are_newer", shell)
        self.assertIn("terminal_sources_are_newer", shell)
        self.assertLess(
            shell.index("ensure_runtime_binaries", shell.index("run_app()")),
            shell.index('echo "Starting CAMS..."', shell.index("run_app()")),
        )

    def test_terminal_check_accepts_configured_executable(self) -> None:
        launcher = APP_ROOT / "cams.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            terminal = Path(temp_dir) / "custom-terminal"
            terminal.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            terminal.chmod(0o700)
            environment = os.environ.copy()
            environment["CAMS_TERMINAL_BINARY"] = str(terminal)

            completed = subprocess.run(
                [str(launcher), "terminal-check"],
                text=True,
                capture_output=True,
                cwd=APP_ROOT,
                env=environment,
                timeout=10,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(str(terminal), completed.stdout)

    def test_terminal_check_rejects_missing_configured_binary(self) -> None:
        environment = os.environ.copy()
        environment["CAMS_TERMINAL_BINARY"] = "/missing/cams-terminal"

        completed = subprocess.run(
            [str(APP_ROOT / "cams.sh"), "terminal-check"],
            text=True,
            capture_output=True,
            cwd=APP_ROOT,
            env=environment,
            timeout=10,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("does not point to a file", completed.stderr)

    def test_vendored_terminal_exposes_managed_contract(self) -> None:
        terminal_root = APP_ROOT / "vendor" / "alacritty" / "alacritty"
        cargo = (terminal_root / "Cargo.toml").read_text(encoding="utf-8")
        cli = (terminal_root / "src" / "cli.rs").read_text(encoding="utf-8")
        nttp = (terminal_root / "src" / "cams.rs").read_text(encoding="utf-8")

        self.assertIn('name = "cams-terminal"', cargo)
        for argument in (
            "nt_managed",
            "nt_session_id",
            "nt_device_id",
            "nt_device_name",
            "nt_host",
            "nt_ipc",
        ):
            self.assertIn(argument, cli)
        for command in (
            "window.focus",
            "window.close",
            "window.set_title",
            "session.ping",
            "session.get_info",
        ):
            self.assertIn(command, nttp)
        main = (terminal_root / "src" / "main.rs").read_text(encoding="utf-8")
        self.assertIn("options.window_options.terminal_options.hold = true", main)

    def test_windows_can_replace_blocked_cython_wheel(self) -> None:
        batch = (APP_ROOT / "cams.bat").read_text(encoding="utf-8")

        self.assertIn("set \"NO_CYTHON_COMPILE=true\"", batch)
        self.assertIn("--reinstall-package cython", batch)
        self.assertIn("--no-binary-package cython", batch)

    @unittest.skipUnless(os.name == "nt", "Windows batch launcher test")
    def test_windows_menu_full_setup_dispatches_without_nested_call(self) -> None:
        batch_path = APP_ROOT / "cams.bat"
        batch = batch_path.read_text(encoding="utf-8")
        self.assertNotIn("call :", batch)

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_uv = Path(temp_dir) / "uv.cmd"
            fake_uv.write_text(
                '@echo off\r\nif /I "%~1"=="--version" echo uv-test 0.0\r\nexit /b 0\r\n',
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["PATH"] = temp_dir + os.pathsep + environment.get("PATH", "")

            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", str(batch_path)],
                input="6\n",
                text=True,
                capture_output=True,
                cwd=APP_ROOT,
                env=environment,
                timeout=30,
                check=False,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        self.assertEqual(output.count("uv-test 0.0"), 3, output)
        self.assertNotIn("cannot find the batch label", output.lower())


if __name__ == "__main__":
    unittest.main()
