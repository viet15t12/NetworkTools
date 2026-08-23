from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class LauncherContractTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX shell launcher test")
    def test_optional_setup_skips_native_build_without_python_headers(self) -> None:
        shell_path = APP_ROOT / "networktools.sh"
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
        batch = (APP_ROOT / "networktools.bat").read_text(encoding="utf-8")
        shell = (APP_ROOT / "networktools.sh").read_text(encoding="utf-8")

        self.assertIn('"%~f0" build', batch)
        self.assertIn("build_cython_optional", shell)
        self.assertIn("sync engine fallback", batch)
        self.assertIn("sync engine fallback", shell)
        self.assertIn("has_python_headers", shell)
        self.assertIn("Skipping optional Cython acceleration", shell)

    def test_explicit_build_stays_strict(self) -> None:
        batch = (APP_ROOT / "networktools.bat").read_text(encoding="utf-8")
        shell = (APP_ROOT / "networktools.sh").read_text(encoding="utf-8")

        self.assertIn('if /I "%~1"=="build" goto build', batch)
        self.assertIn("build) build_cython ;;", shell)
        self.assertIn("require_python_headers", shell)

    def test_setup_checks_optional_terminal_companion(self) -> None:
        shell = (APP_ROOT / "networktools.sh").read_text(encoding="utf-8")

        self.assertIn("check_terminal_optional", shell)
        self.assertIn("build_terminal_optional", shell)
        self.assertIn("terminal-check) check_terminal", shell)
        self.assertIn("terminal-build) build_terminal", shell)
        self.assertIn("NETWORKTOOLS_TERMINAL_BINARY", shell)
        self.assertIn("--bin networktools-terminal", shell)
        self.assertIn("prepare_environment", shell)
        self.assertIn("unset VIRTUAL_ENV", shell)
        self.assertIn('/.cargo}/env"', shell)

    def test_run_checks_cpp_and_rust_binaries_before_starting_python(self) -> None:
        shell = (APP_ROOT / "networktools.sh").read_text(encoding="utf-8")

        self.assertIn("ensure_runtime_binaries", shell)
        self.assertIn("ensure_syslog_collector", shell)
        self.assertIn("ensure_terminal", shell)
        self.assertIn("syslog_sources_are_newer", shell)
        self.assertIn("terminal_sources_are_newer", shell)
        self.assertLess(
            shell.index("ensure_runtime_binaries", shell.index("run_app()")),
            shell.index('echo "Starting NetworkTools..."', shell.index("run_app()")),
        )

    def test_terminal_check_accepts_configured_executable(self) -> None:
        launcher = APP_ROOT / "networktools.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            terminal = Path(temp_dir) / "custom-terminal"
            terminal.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            terminal.chmod(0o700)
            environment = os.environ.copy()
            environment["NETWORKTOOLS_TERMINAL_BINARY"] = str(terminal)

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
        environment["NETWORKTOOLS_TERMINAL_BINARY"] = "/missing/networktools-terminal"

        completed = subprocess.run(
            [str(APP_ROOT / "networktools.sh"), "terminal-check"],
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
        nttp = (terminal_root / "src" / "networktools.rs").read_text(encoding="utf-8")

        self.assertIn('name = "networktools-terminal"', cargo)
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
        batch = (APP_ROOT / "networktools.bat").read_text(encoding="utf-8")

        self.assertIn("set \"NO_CYTHON_COMPILE=true\"", batch)
        self.assertIn("--reinstall-package cython", batch)
        self.assertIn("--no-binary-package cython", batch)

    @unittest.skipUnless(os.name == "nt", "Windows batch launcher test")
    def test_windows_menu_full_setup_dispatches_without_nested_call(self) -> None:
        batch_path = APP_ROOT / "networktools.bat"
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
