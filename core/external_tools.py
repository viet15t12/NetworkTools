"""QML facade for external-tool catalog, discovery, and launching."""

from __future__ import annotations

import os
import re
import shlex
import shutil
from infrastructure.database import sqlcipher as sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot

from core.app_paths import APP_DIR
from core.tool_catalog import EXTERNAL_TOOL_CATALOG
from features.devices import DeviceLoginService, DeviceRepository
from infrastructure.database.paths import DEVICE_NETWORK_DB
from infrastructure.system.network_info import _decode_command_output

DB_PATH = DEVICE_NETWORK_DB
EXTERNAL_TOOLS_DB_PATH = APP_DIR / "external_tools.db"
_device_login_service = DeviceLoginService(DeviceRepository(DB_PATH))


def load_device_for_login(host: str) -> dict[str, Any] | None:
    """Load normalized device credentials for the external CLI launcher."""
    return _device_login_service.load(host)

class ExternalToolsManager(QObject):
    toolsChanged = pyqtSignal()
    browserChanged = pyqtSignal()

    TOOL_TYPES = ("SSH Client", "SFTP Client", "Terminal", "DB Browser")
    DEFAULT_TERMINAL_AUTOMATIC_GUID = "{00000000-0000-0000-0000-000000000000}"
    DEFAULT_CONSOLE_HOST_GUID = "{B23D10C0-E52E-411E-9D5B-C09FDF709C7D}"
    DEFAULT_WINDOWS_TERMINAL_GUID = "{E12CFF52-A866-4C77-9A90-F570A7AA2C6B}"
    DEFAULT_WINDOWS_TERMINAL_PREVIEW_GUID = "{86633F1F-6454-40EC-89CE-DA4EBA977EE2}"

    WINDOWS_TOOL_SPECS: tuple[dict[str, Any], ...] = (
        {
            "app": "PuTTY",
            "type": "SSH Client",
            "executables": ("putty.exe",),
            "arguments": "-ssh {ip}",
            "description": "SSH client detected on Windows.",
            "known_paths": (
                "%ProgramFiles%\\PuTTY\\putty.exe",
                "%ProgramFiles(x86)%\\PuTTY\\putty.exe",
                "%LOCALAPPDATA%\\Programs\\PuTTY\\putty.exe",
            ),
        },
        {
            "app": "Xshell",
            "type": "SSH Client",
            "executables": ("Xshell.exe",),
            "arguments": "-url ssh://{ip}",
            "description": "NetSarang Xshell SSH client detected on Windows.",
            "uninstall_names": ("Xshell",),
            "known_paths": (
                "%ProgramFiles%\\NetSarang\\Xshell 9\\Xshell.exe",
                "%ProgramFiles%\\NetSarang\\Xshell 8\\Xshell.exe",
                "%ProgramFiles%\\NetSarang\\Xshell 7\\Xshell.exe",
                "%ProgramFiles(x86)%\\NetSarang\\Xshell 9\\Xshell.exe",
                "%ProgramFiles(x86)%\\NetSarang\\Xshell 8\\Xshell.exe",
                "%ProgramFiles(x86)%\\NetSarang\\Xshell 7\\Xshell.exe",
            ),
        },
        {
            "app": "MobaXterm",
            "type": "SSH Client",
            "executables": ("MobaXterm.exe",),
            "arguments": "-newtab \"ssh {ip}\"",
            "description": "MobaXterm remote terminal and SSH client detected on Windows.",
            "uninstall_names": ("MobaXterm",),
            "known_paths": (
                "%ProgramFiles%\\Mobatek\\MobaXterm\\MobaXterm.exe",
                "%ProgramFiles(x86)%\\Mobatek\\MobaXterm\\MobaXterm.exe",
                "%LOCALAPPDATA%\\Programs\\MobaXterm\\MobaXterm.exe",
            ),
        },
        {
            "app": "Tera Term",
            "type": "SSH Client",
            "executables": ("ttermpro.exe",),
            "arguments": "{ip} /ssh /2",
            "description": "Tera Term SSH terminal detected on Windows.",
            "uninstall_names": ("Tera Term", "TeraTerm"),
            "known_paths": (
                "%ProgramFiles%\\teraterm5\\ttermpro.exe",
                "%ProgramFiles(x86)%\\teraterm5\\ttermpro.exe",
                "%ProgramFiles%\\teraterm\\ttermpro.exe",
                "%ProgramFiles(x86)%\\teraterm\\ttermpro.exe",
            ),
        },
        {
            "app": "SecureCRT",
            "type": "SSH Client",
            "executables": ("SecureCRT.exe",),
            "arguments": "/SSH2 {ip}",
            "description": "SecureCRT client detected on Windows.",
            "known_paths": (
                "%ProgramFiles%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
                "%ProgramFiles(x86)%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
                "%LOCALAPPDATA%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
            ),
        },
        {
            "app": "WinSCP",
            "type": "SFTP Client",
            "executables": ("WinSCP.exe",),
            "arguments": "sftp://{username}@{ip}:{port}{path}",
            "description": "WinSCP SFTP client detected on Windows.",
            "uninstall_names": ("WinSCP",),
            "known_paths": (
                "%ProgramFiles%\\WinSCP\\WinSCP.exe",
                "%ProgramFiles(x86)%\\WinSCP\\WinSCP.exe",
                "%LOCALAPPDATA%\\Programs\\WinSCP\\WinSCP.exe",
            ),
        },
        {
            "app": "Windows Terminal",
            "type": "Terminal",
            "executables": ("wt.exe",),
            "arguments": "",
            "description": "Modern terminal installed through Windows or Microsoft Store.",
            "known_paths": ("%LOCALAPPDATA%\\Microsoft\\WindowsApps\\wt.exe",),
        },
        {
            "app": "Command Prompt",
            "type": "Terminal",
            "executables": ("cmd.exe",),
            "arguments": "",
            "description": "Windows Console Host command prompt.",
            "known_paths": ("%SystemRoot%\\System32\\cmd.exe",),
        },
        {
            "app": "DB Browser for SQLite",
            "type": "DB Browser",
            "executables": ("DB Browser for SQLite.exe", "sqlitebrowser.exe"),
            "arguments": "{db}",
            "description": "SQLite database browser detected on Windows.",
            "known_paths": (
                "%ProgramFiles%\\DB Browser for SQLite\\DB Browser for SQLite.exe",
                "%ProgramFiles(x86)%\\DB Browser for SQLite\\DB Browser for SQLite.exe",
                "%LOCALAPPDATA%\\Programs\\DB Browser for SQLite\\DB Browser for SQLite.exe",
            ),
        },
        {
            "app": "SQLiteStudio",
            "type": "DB Browser",
            "executables": ("SQLiteStudio.exe", "sqlitestudio.exe"),
            "arguments": "{db}",
            "description": "SQLiteStudio database browser detected on Windows.",
            "known_paths": (
                "%ProgramFiles%\\SQLiteStudio\\SQLiteStudio.exe",
                "%LOCALAPPDATA%\\Programs\\SQLiteStudio\\SQLiteStudio.exe",
            ),
        },
        {
            "app": "Letos",
            "type": "DB Browser",
            "executables": ("Letos.exe", "letos.exe"),
            "arguments": "{db}",
            "description": "Letos SQLite database manager detected on Windows.",
            "uninstall_names": ("Letos",),
            "known_paths": (
                "%ProgramFiles%\\Letos\\Letos.exe",
                "%LOCALAPPDATA%\\Programs\\Letos\\Letos.exe",
            ),
        },
    )

    LINUX_TOOL_SPECS: tuple[dict[str, Any], ...] = (
        {
            "app": "PuTTY",
            "type": "SSH Client",
            "executables": ("putty",),
            "arguments": "-ssh {ip}",
            "description": "PuTTY SSH client installed on Linux.",
            "known_paths": ("/usr/bin/putty", "/usr/local/bin/putty"),
        },
        {
            "app": "Remmina",
            "type": "SSH Client",
            "executables": ("remmina",),
            "arguments": "-c ssh://{ip}",
            "description": "Remote desktop client with SSH support.",
            "known_paths": ("/usr/bin/remmina", "/usr/local/bin/remmina"),
        },
        {
            "app": "FileZilla",
            "type": "SFTP Client",
            "executables": ("filezilla",),
            "arguments": "sftp://{username}@{ip}:{port}{path}",
            "description": "FileZilla SFTP client installed on Linux.",
            "known_paths": ("/usr/bin/filezilla", "/usr/local/bin/filezilla"),
        },
        {
            "app": "Terminal",
            "type": "Terminal",
            "executables": ("xdg-terminal-exec", "x-terminal-emulator"),
            "arguments": "",
            "description": "The terminal selected by the Linux desktop.",
            "known_paths": ("/usr/bin/xdg-terminal-exec", "/usr/bin/x-terminal-emulator"),
        },
        {
            "app": "GNOME Console",
            "type": "Terminal",
            "executables": ("kgx",),
            "arguments": "",
            "description": "GNOME Console terminal host.",
            "known_paths": ("/usr/bin/kgx",),
        },
        {
            "app": "GNOME Terminal",
            "type": "Terminal",
            "executables": ("gnome-terminal",),
            "arguments": "",
            "description": "GNOME terminal host.",
            "known_paths": ("/usr/bin/gnome-terminal",),
        },
        {
            "app": "Konsole",
            "type": "Terminal",
            "executables": ("konsole",),
            "arguments": "",
            "description": "KDE terminal host.",
            "known_paths": ("/usr/bin/konsole",),
        },
        {
            "app": "DB Browser for SQLite",
            "type": "DB Browser",
            "executables": ("sqlitebrowser",),
            "arguments": "{db}",
            "description": "SQLite database browser installed on Linux.",
            "known_paths": ("/usr/bin/sqlitebrowser", "/usr/local/bin/sqlitebrowser"),
        },
        {
            "app": "SQLiteStudio",
            "type": "DB Browser",
            "executables": ("sqlitestudio",),
            "arguments": "{db}",
            "description": "SQLiteStudio database browser installed on Linux.",
            "known_paths": ("/usr/bin/sqlitestudio", "/usr/local/bin/sqlitestudio"),
        },
        {
            "app": "Letos",
            "type": "DB Browser",
            "executables": ("letos",),
            "arguments": "{db}",
            "description": "Letos SQLite database manager installed on Linux.",
            "known_paths": ("/usr/bin/letos", "/usr/local/bin/letos"),
        },
    )

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        db_path: str | Path | None = None,
        device_db_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.db_path = Path(db_path) if db_path is not None else EXTERNAL_TOOLS_DB_PATH
        self.device_db_path = Path(device_db_path) if device_db_path is not None else DB_PATH
        self._active_table = ""
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS apps (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    app         TEXT NOT NULL UNIQUE,
                    type        TEXT NOT NULL,
                    executable  TEXT NOT NULL,
                    arguments   TEXT DEFAULT '',
                    enabled     INTEGER DEFAULT 1,
                    description TEXT DEFAULT ''
                );
                """
            )
            conn.commit()

    def _dict_rows(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _file_url_to_path(self, value: str) -> Path:
        text = (value or "").strip()
        parsed = QUrl(text)
        if parsed.isLocalFile():
            return Path(parsed.toLocalFile())
        return Path(text)

    def _normalized_executable_path(self, value: str) -> Path:
        path = self._file_url_to_path(value)
        expanded = os.path.expanduser(os.path.expandvars(str(path)))
        return Path(expanded.strip().strip('"'))

    def _path_key(self, value: str | Path) -> str:
        text = os.path.normcase(os.path.normpath(str(value)))
        return text.casefold()

    def _windows_registry_value(self, root: Any, key_path: str, value_name: str | None = None) -> str:
        if sys.platform != "win32":
            return ""
        try:
            import winreg
        except ImportError:
            return ""

        access_modes = (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
        for access in access_modes:
            try:
                with winreg.OpenKey(root, key_path, 0, access) as key:
                    value, _ = winreg.QueryValueEx(key, value_name or "")
                    return os.path.expandvars(str(value or "")).strip()
            except OSError:
                continue
        return ""

    def _windows_app_path(self, executable_name: str) -> str:
        if sys.platform != "win32":
            return ""
        try:
            import winreg
        except ImportError:
            return ""
        key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}"
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            value = self._windows_registry_value(root, key_path)
            if value:
                return value.strip('"')
        return ""

    def _extract_executable_from_command(self, command: str) -> str:
        text = os.path.expandvars(str(command or "").strip())
        if not text:
            return ""
        if text.startswith('"'):
            closing_quote = text.find('"', 1)
            if closing_quote > 1:
                return text[1:closing_quote]
        match = re.match(r"^(.+?\.(?:exe|com|bat|cmd))(?=\s|$)", text, re.IGNORECASE)
        return match.group(1).strip().strip('"') if match else ""

    def _windows_association_handler(self, association: str, protocol: bool) -> dict[str, Any] | None:
        if sys.platform != "win32":
            return None
        try:
            import winreg
        except ImportError:
            return None

        if protocol:
            user_choice = rf"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\{association}\UserChoice"
        else:
            user_choice = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{association}\UserChoice"
        prog_id = self._windows_registry_value(winreg.HKEY_CURRENT_USER, user_choice, "ProgId")
        explicit = bool(prog_id)
        if not prog_id:
            prog_id = self._windows_registry_value(winreg.HKEY_CLASSES_ROOT, association)
        if not prog_id:
            return None
        command = self._windows_registry_value(
            winreg.HKEY_CLASSES_ROOT,
            rf"{prog_id}\shell\open\command",
        )
        executable = self._extract_executable_from_command(command)
        if not executable:
            return None
        return {
            "executable": executable,
            "association": association,
            "explicit": explicit,
            "progId": prog_id,
        }

    def _windows_default_handlers(self) -> list[dict[str, Any]]:
        if sys.platform != "win32":
            return []
        handlers: list[dict[str, Any]] = []
        for association, app_type, protocol in (
            ("ssh", "SSH Client", True),
            ("telnet", "SSH Client", True),
            ("sftp", "SFTP Client", True),
            (".db", "DB Browser", False),
            (".sqlite", "DB Browser", False),
            (".sqlite3", "DB Browser", False),
        ):
            handler = self._windows_association_handler(association, protocol)
            if handler:
                handler["type"] = app_type
                handlers.append(handler)

        try:
            import winreg
        except ImportError:
            return handlers
        delegation = self._windows_registry_value(
            winreg.HKEY_CURRENT_USER,
            r"Console\%%Startup",
            "DelegationTerminal",
        )
        delegation_key = delegation.casefold()
        automatic_key = self.DEFAULT_TERMINAL_AUTOMATIC_GUID.casefold()
        console_host_key = self.DEFAULT_CONSOLE_HOST_GUID.casefold()
        terminal_keys = {
            self.DEFAULT_WINDOWS_TERMINAL_GUID.casefold(),
            self.DEFAULT_WINDOWS_TERMINAL_PREVIEW_GUID.casefold(),
        }

        if delegation_key == console_host_key:
            command_prompt = shutil.which("cmd.exe") or os.path.expandvars(r"%SystemRoot%\System32\cmd.exe")
            handlers.append({
                "executable": command_prompt,
                "association": "Default terminal",
                "explicit": True,
                "type": "Terminal",
            })
        elif delegation_key in terminal_keys or not delegation or delegation_key == automatic_key:
            terminal_path = self._windows_app_path("wt.exe") or shutil.which("wt.exe") or ""
            if terminal_path:
                handlers.append({
                    "executable": terminal_path,
                    "association": "Default terminal",
                    "explicit": delegation_key in terminal_keys,
                    "type": "Terminal",
                })
            else:
                command_prompt = shutil.which("cmd.exe") or os.path.expandvars(r"%SystemRoot%\System32\cmd.exe")
                handlers.append({
                    "executable": command_prompt,
                    "association": "Default terminal",
                    "explicit": False,
                    "type": "Terminal",
                })
        else:
            clsid_paths = (
                rf"CLSID\{delegation}\LocalServer32",
                rf"CLSID\{delegation}\InprocServer32",
            )
            delegation_command = ""
            for clsid_path in clsid_paths:
                delegation_command = self._windows_registry_value(winreg.HKEY_CLASSES_ROOT, clsid_path)
                if delegation_command:
                    break
            marker = delegation_command.casefold()
            if "windowsterminal" in marker or "openconsole" in marker:
                terminal_path = self._windows_app_path("wt.exe") or shutil.which("wt.exe") or ""
                if terminal_path:
                    handlers.append({
                        "executable": terminal_path,
                        "association": "Default terminal",
                        "explicit": True,
                        "type": "Terminal",
                    })
        return handlers

    def _linux_desktop_entry(self, desktop_id: str) -> dict[str, str] | None:
        if not sys.platform.startswith("linux"):
            return None
        desktop_name = str(desktop_id or "").strip()
        if not desktop_name:
            return None
        for applications_dir in self._linux_application_dirs():
            desktop_path = applications_dir / desktop_name
            if not desktop_path.is_file():
                continue
            entry = self._parse_linux_desktop_entry(desktop_path)
            if entry:
                entry["DesktopId"] = desktop_name
                return entry
        return None

    def _linux_application_dirs(self) -> list[Path]:
        data_home = Path(
            os.environ.get("XDG_DATA_HOME")
            or (Path.home() / ".local" / "share")
        )
        data_dirs = [
            Path(value)
            for value in (
                os.environ.get("XDG_DATA_DIRS")
                or "/usr/local/share:/usr/share"
            ).split(os.pathsep)
            if value
        ]
        candidates = (
            data_home / "applications",
            *(data_dir / "applications" for data_dir in data_dirs),
            data_home / "flatpak" / "exports" / "share" / "applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path("/var/lib/snapd/desktop/applications"),
        )
        directories: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = self._path_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            directories.append(candidate)
        return directories

    def _parse_linux_desktop_entry(
        self,
        desktop_path: Path,
    ) -> dict[str, str] | None:
        values: dict[str, str] = {}
        wanted = {
            "Name",
            "Comment",
            "Exec",
            "TryExec",
            "Type",
            "Hidden",
            "NoDisplay",
            "Categories",
            "MimeType",
        }
        in_desktop_entry = False
        try:
            lines = desktop_path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            return None
        for raw_line in lines:
            line = raw_line.strip()
            if line.startswith("[") and line.endswith("]"):
                in_desktop_entry = line == "[Desktop Entry]"
                continue
            if not in_desktop_entry or "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key in wanted and key not in values:
                values[key] = value.strip()
        if values.get("Exec"):
            return values
        return None

    def _linux_exec_path(self, command: str) -> str:
        executable, _ = self._linux_exec_details(command)
        return executable

    def _linux_exec_details(self, command: str) -> tuple[str, list[str]]:
        try:
            tokens = shlex.split(str(command or ""), posix=True)
        except ValueError:
            return "", []
        while tokens and Path(tokens[0]).name == "env":
            tokens.pop(0)
            while tokens:
                token = tokens[0]
                if token == "--":
                    tokens.pop(0)
                    break
                if token in {"-u", "--unset"}:
                    del tokens[:2]
                    continue
                if "=" in token or token.startswith("-"):
                    tokens.pop(0)
                    continue
                break
        if not tokens:
            return "", []
        executable_name = tokens.pop(0)
        executable = (
            executable_name
            if executable_name.startswith("/")
            else (shutil.which(executable_name) or "")
        )
        if not executable:
            return "", []

        # Desktop Exec field codes are targets supplied by the desktop shell.
        # CAMS supplies its own safe placeholders when launching.
        arguments: list[str] = []
        field_code = re.compile(r"%(?:[fFuUdDnNickvm])")
        for token in tokens:
            cleaned = field_code.sub("", token).replace("%%", "%")
            if cleaned:
                arguments.append(cleaned)
        return executable, arguments

    def _linux_desktop_types(self, entry: dict[str, str]) -> list[str]:
        categories = {
            value
            for value in entry.get("Categories", "").split(";")
            if value
        }
        mime_types = {
            value
            for value in entry.get("MimeType", "").split(";")
            if value
        }
        tool_types: list[str] = []
        if mime_types.intersection({
            "x-scheme-handler/ssh",
            "x-scheme-handler/telnet",
        }):
            tool_types.append("SSH Client")
        if "x-scheme-handler/sftp" in mime_types:
            tool_types.append("SFTP Client")
        if mime_types.intersection({
            "application/x-sqlite3",
            "application/vnd.sqlite3",
            "application/x-sqlite",
        }):
            tool_types.append("DB Browser")
        if "TerminalEmulator" in categories:
            tool_types.append("Terminal")
        return tool_types

    def _linux_desktop_spec(
        self,
        entry: dict[str, str],
        app_type: str,
    ) -> tuple[dict[str, Any], str] | None:
        executable, launch_prefix = self._linux_exec_details(
            entry.get("Exec", "")
        )
        if not executable or not Path(executable).is_file():
            return None
        spec = self._tool_spec_for_path(executable, app_type)
        spec["app"] = entry.get("Name") or spec["app"]
        default_arguments = str(spec.get("arguments") or "")
        combined_arguments = [
            *launch_prefix,
            *(
                shlex.split(default_arguments, posix=True)
                if default_arguments
                else []
            ),
        ]
        spec["arguments"] = shlex.join(combined_arguments)
        spec["description"] = (
            entry.get("Comment")
            or "Application registered with the Linux desktop."
        )
        # Runners such as Flatpak use one executable for many applications.
        if Path(executable).name in {"flatpak", "snap"}:
            spec["candidateIdentity"] = entry.get("DesktopId", "")
        return spec, executable

    def _linux_desktop_specs(
        self,
    ) -> list[tuple[dict[str, Any], str]]:
        if not sys.platform.startswith("linux"):
            return []
        candidates: list[tuple[dict[str, Any], str]] = []
        seen_desktop_ids: set[str] = set()
        for applications_dir in self._linux_application_dirs():
            if not applications_dir.is_dir():
                continue
            try:
                desktop_paths = sorted(applications_dir.glob("*.desktop"))
            except OSError:
                continue
            for desktop_path in desktop_paths:
                desktop_id = desktop_path.name
                if desktop_id in seen_desktop_ids:
                    continue
                seen_desktop_ids.add(desktop_id)
                entry = self._parse_linux_desktop_entry(desktop_path)
                if not entry:
                    continue
                entry["DesktopId"] = desktop_id
                if entry.get("Type", "Application") != "Application":
                    continue
                if (
                    entry.get("Hidden", "").casefold() == "true"
                    or entry.get("NoDisplay", "").casefold() == "true"
                ):
                    continue
                tool_types = self._linux_desktop_types(entry)
                if not tool_types:
                    continue
                try_exec = entry.get("TryExec", "")
                if try_exec and not self._linux_exec_path(try_exec):
                    continue
                for app_type in tool_types:
                    candidate = self._linux_desktop_spec(entry, app_type)
                    if candidate:
                        candidates.append(candidate)
        return candidates

    def _linux_default_handlers(self) -> list[dict[str, Any]]:
        if not sys.platform.startswith("linux"):
            return []
        handlers: list[dict[str, Any]] = []
        xdg_mime = shutil.which("xdg-mime")
        associations = (
            ("x-scheme-handler/ssh", "SSH Client", "ssh"),
            ("x-scheme-handler/telnet", "SSH Client", "telnet"),
            ("x-scheme-handler/sftp", "SFTP Client", "sftp"),
            ("application/x-sqlite3", "DB Browser", "SQLite database"),
            ("application/vnd.sqlite3", "DB Browser", "SQLite database"),
        )
        if xdg_mime:
            for mime_type, app_type, label in associations:
                try:
                    result = subprocess.run(
                        [xdg_mime, "query", "default", mime_type],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                desktop_id = result.stdout.strip()
                entry = self._linux_desktop_entry(desktop_id)
                candidate = (
                    self._linux_desktop_spec(entry, app_type)
                    if entry
                    else None
                )
                if not candidate:
                    continue
                spec, executable = candidate
                handlers.append({
                    "executable": executable,
                    "association": label,
                    "explicit": True,
                    "type": app_type,
                    "app": spec["app"],
                    "arguments": spec["arguments"],
                    "description": spec["description"],
                    "candidateIdentity": spec.get("candidateIdentity", ""),
                })

        terminal = os.environ.get("TERMINAL", "").strip()
        terminal_path = self._linux_exec_path(terminal) if terminal else ""
        explicit_terminal = bool(terminal_path)
        if not terminal_path:
            for executable_name in ("xdg-terminal-exec", "x-terminal-emulator"):
                terminal_path = shutil.which(executable_name) or ""
                if terminal_path:
                    break
        if terminal_path:
            handlers.append({
                "executable": terminal_path,
                "association": "Default terminal",
                "explicit": explicit_terminal,
                "type": "Terminal",
            })
        return handlers

    def _tool_spec_for_path(self, executable: str, app_type: str = "") -> dict[str, Any]:
        name = Path(executable).name.casefold()
        for spec in (*self.WINDOWS_TOOL_SPECS, *self.LINUX_TOOL_SPECS):
            if name in {candidate.casefold() for candidate in spec["executables"]}:
                return dict(spec)
        display_name = Path(executable).stem.replace("_", " ").strip() or "Application"
        if app_type == "DB Browser":
            arguments = "{db}"
        elif app_type == "SFTP Client":
            arguments = "sftp://{username}@{ip}:{port}{path}"
        elif app_type == "SSH Client":
            arguments = "{ip}"
        else:
            arguments = ""
        return {
            "app": display_name,
            "type": app_type or "Terminal",
            "executables": (Path(executable).name,),
            "arguments": arguments,
            "description": "Application registered with the operating system.",
            "known_paths": (),
        }

    def _windows_uninstall_paths(self, spec: dict[str, Any]) -> list[str]:
        if sys.platform != "win32":
            return []
        try:
            import winreg
        except ImportError:
            return []

        name_patterns = tuple(
            str(value).strip().casefold()
            for value in spec.get("uninstall_names", ())
            if str(value).strip()
        )
        if not name_patterns:
            return []

        executable_names = {
            str(value).casefold()
            for value in spec.get("executables", ())
        }
        found: list[str] = []
        seen: set[str] = set()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        access_modes = (
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
        )

        def read_value(key: Any, value_name: str) -> str:
            try:
                value, _ = winreg.QueryValueEx(key, value_name)
                return os.path.expandvars(str(value or "")).strip()
            except OSError:
                return ""

        def add(candidate: str | Path) -> None:
            path = self._normalized_executable_path(str(candidate))
            if not path.is_file() or path.name.casefold() not in executable_names:
                return
            normalized = self._path_key(path)
            if normalized in seen:
                return
            seen.add(normalized)
            found.append(str(path))

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for access in access_modes:
                try:
                    uninstall_key = winreg.OpenKey(root, key_path, 0, access)
                except OSError:
                    continue
                with uninstall_key:
                    index = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(uninstall_key, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            application_key = winreg.OpenKey(uninstall_key, subkey_name, 0, access)
                        except OSError:
                            continue
                        with application_key:
                            display_name = read_value(application_key, "DisplayName").casefold()
                            if not any(pattern in display_name for pattern in name_patterns):
                                continue
                            install_location = read_value(application_key, "InstallLocation")
                            if install_location:
                                for executable_name in spec.get("executables", ()):
                                    add(Path(install_location) / str(executable_name))
                            display_icon = self._extract_executable_from_command(
                                read_value(application_key, "DisplayIcon").split(",", 1)[0]
                            )
                            if display_icon:
                                add(display_icon)
        return found

    def _installed_paths_for_spec(self, spec: dict[str, Any]) -> list[tuple[str, str, str]]:
        paths: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        def add(value: str | Path, source: str, confidence: str) -> None:
            if not value:
                return
            path = self._normalized_executable_path(str(value))
            if not path.is_file():
                return
            key = self._path_key(path)
            if key in seen:
                return
            seen.add(key)
            paths.append((str(path), source, confidence))

        for executable_name in spec["executables"]:
            if sys.platform == "win32":
                add(self._windows_app_path(executable_name), "Windows App Paths", "High")
                add(shutil.which(executable_name) or "", "PATH / App Execution Alias", "Medium")
            else:
                add(shutil.which(executable_name) or "", "PATH", "High")
        if sys.platform == "win32":
            for installed_path in self._windows_uninstall_paths(spec):
                add(installed_path, "Windows installed applications", "High")
        for known_path in spec.get("known_paths", ()):
            add(known_path, "Known install location", "Medium")
        return paths

    def _configured_tool_keys(self) -> tuple[set[str], set[str]]:
        configured_paths: set[str] = set()
        configured_apps: set[str] = set()
        for tool in self.getTools():
            configured_apps.add(str(tool.get("app") or "").strip().casefold())
            executable = str(tool.get("executable") or "").strip()
            if executable:
                configured_paths.add(self._path_key(self._normalized_executable_path(executable)))
        return configured_paths, configured_apps

    def _discovery_row(
        self,
        spec: dict[str, Any],
        executable: str,
        source: str,
        confidence: str,
        *,
        default_for: list[str] | None = None,
        explicit_default: bool = False,
    ) -> dict[str, Any]:
        identity = str(spec.get("candidateIdentity") or "")
        candidate_path = self._path_key(executable)
        if identity:
            candidate_path = f"{candidate_path}|{identity.casefold()}"
        return {
            "candidateId": f"{spec['type']}|{candidate_path}",
            "app": spec["app"],
            "type": spec["type"],
            "executable": str(self._normalized_executable_path(executable)),
            "arguments": spec.get("arguments", ""),
            "description": spec.get("description", ""),
            "source": source,
            "confidence": confidence,
            "isDefault": bool(default_for),
            "explicitDefault": explicit_default,
            "defaultFor": list(default_for or []),
            "alreadyConfigured": False,
            "isAmbiguous": False,
        }

    @pyqtSlot(str, result="QVariant")
    def validateExecutable(self, executable: str) -> dict[str, Any]:
        text = str(executable or "").strip()
        if not text:
            return {"ok": False, "exists": False, "path": "", "message": "Executable path is required."}
        path = self._normalized_executable_path(text)
        normalized = str(path)
        if not path.is_file():
            return {"ok": False, "exists": False, "path": normalized, "message": "Executable file was not found."}
        if sys.platform == "win32" and path.suffix.casefold() not in {".exe", ".com", ".bat", ".cmd"}:
            return {"ok": False, "exists": True, "path": normalized, "message": "Choose a Windows executable (.exe, .com, .bat, or .cmd)."}
        return {"ok": True, "exists": True, "path": normalized, "message": "Executable is available."}

    @pyqtSlot(result="QVariant")
    def discoverExternalTools(self) -> list[dict[str, Any]]:
        if sys.platform == "win32":
            specs = self.WINDOWS_TOOL_SPECS
            default_handlers = self._windows_default_handlers()
            default_source = "Windows default association"
        elif sys.platform.startswith("linux"):
            specs = self.LINUX_TOOL_SPECS
            default_handlers = self._linux_default_handlers()
            default_source = "Linux default application"
        else:
            return []

        rows_by_key: dict[str, dict[str, Any]] = {}
        for spec in specs:
            for executable, source, confidence in self._installed_paths_for_spec(spec):
                row = self._discovery_row(spec, executable, source, confidence)
                rows_by_key[row["candidateId"]] = row
        if sys.platform.startswith("linux"):
            for spec, executable in self._linux_desktop_specs():
                row = self._discovery_row(
                    spec,
                    executable,
                    "Linux desktop application",
                    "High",
                )
                rows_by_key.setdefault(row["candidateId"], row)

        for handler in default_handlers:
            executable = str(handler.get("executable") or "")
            validation = self.validateExecutable(executable)
            if not validation.get("ok"):
                continue
            spec = self._tool_spec_for_path(validation["path"], str(handler.get("type") or ""))
            if handler.get("app"):
                spec["app"] = str(handler["app"])
            if "arguments" in handler:
                spec["arguments"] = str(handler.get("arguments") or "")
            if handler.get("description"):
                spec["description"] = str(handler["description"])
            if handler.get("candidateIdentity"):
                spec["candidateIdentity"] = str(handler["candidateIdentity"])
            row = self._discovery_row(
                spec,
                validation["path"],
                default_source,
                "High" if handler.get("explicit") else "Medium",
                default_for=[str(handler.get("association") or "")],
                explicit_default=bool(handler.get("explicit")),
            )
            existing = rows_by_key.get(row["candidateId"])
            if existing:
                existing["isDefault"] = True
                existing["explicitDefault"] = row["explicitDefault"]
                defaults = list(existing.get("defaultFor") or [])
                if row["defaultFor"][0] not in defaults:
                    defaults.extend(row["defaultFor"])
                existing["defaultFor"] = defaults
                existing["source"] = default_source
                existing["confidence"] = row["confidence"]
            else:
                rows_by_key[row["candidateId"]] = row

        # A terminal host can be exposed both through its real package path and
        # an App Execution Alias (for example two wt.exe paths). The UI chooses
        # a terminal application, not a package binary, so keep one best row per
        # terminal name while retaining multiple installs for SSH/DB tools.
        terminal_by_app: dict[str, tuple[str, dict[str, Any]]] = {}
        for candidate_id, row in list(rows_by_key.items()):
            if row["type"] != "Terminal":
                continue
            app_key = row["app"].casefold()
            current = terminal_by_app.get(app_key)
            score = (
                bool(row.get("isDefault")),
                bool(row.get("explicitDefault")),
                row.get("confidence") == "High",
            )
            if current is None:
                terminal_by_app[app_key] = (candidate_id, row)
                continue
            current_id, current_row = current
            current_score = (
                bool(current_row.get("isDefault")),
                bool(current_row.get("explicitDefault")),
                current_row.get("confidence") == "High",
            )
            if score > current_score:
                rows_by_key.pop(current_id, None)
                terminal_by_app[app_key] = (candidate_id, row)
            else:
                rows_by_key.pop(candidate_id, None)

        configured_paths, configured_apps = self._configured_tool_keys()
        app_counts: dict[tuple[str, str], int] = {}
        for row in rows_by_key.values():
            app_key = (row["type"], row["app"].casefold())
            app_counts[app_key] = app_counts.get(app_key, 0) + 1
            shared_launcher = Path(row["executable"]).name in {
                "flatpak",
                "snap",
            }
            row["alreadyConfigured"] = (
                row["app"].casefold() in configured_apps
                or (
                    not shared_launcher
                    and self._path_key(row["executable"]) in configured_paths
                )
            )
        for row in rows_by_key.values():
            row["isAmbiguous"] = app_counts[(row["type"], row["app"].casefold())] > 1

        return sorted(
            rows_by_key.values(),
            key=lambda row: (
                not row["isDefault"],
                row["type"].casefold(),
                row["app"].casefold(),
                row["executable"].casefold(),
            ),
        )

    @pyqtSlot(result="QVariant")
    def discoverWindowsTools(self) -> list[dict[str, Any]]:
        """Compatibility slot retained for older QML and third-party callers."""
        return self.discoverExternalTools()

    @pyqtSlot(result="QVariant")
    def getExternalToolCatalog(self) -> list[dict[str, Any]]:
        configured_tools = self.getTools()
        configured_paths = {
            self._path_key(
                self._normalized_executable_path(
                    str(tool.get("executable") or "")
                )
            )
            for tool in configured_tools
            if str(tool.get("executable") or "").strip()
        }
        configured_by_app = {
            str(tool.get("app") or "").strip().casefold(): tool
            for tool in configured_tools
        }
        rows: list[dict[str, Any]] = []
        for entry in EXTERNAL_TOOL_CATALOG:
            detected = self._installed_paths_for_spec(entry)
            executable = detected[0][0] if detected else ""
            detection_source = detected[0][1] if detected else ""
            saved_tool = configured_by_app.get(entry["app"].casefold())
            saved_path = (
                self._normalized_executable_path(
                    str(saved_tool.get("executable") or "")
                )
                if saved_tool
                else None
            )
            saved_available = bool(saved_path and saved_path.is_file())
            if not executable and saved_available:
                executable = str(saved_path)
                detection_source = "External Tools configuration"
            installed = bool(executable)
            configured = (
                saved_available
                or (installed and self._path_key(executable) in configured_paths)
            )
            saved_missing = bool(saved_tool and not saved_available)
            enabled = bool(saved_tool and saved_tool.get("enabled") and configured)
            rows.append(
                {
                    "app": entry["app"],
                    "category": entry["category"],
                    "summary": entry["summary"],
                    "officialUrl": entry["officialUrl"],
                    "installed": installed,
                    "configured": configured,
                    "enabled": enabled,
                    "saved": saved_tool is not None,
                    "executable": executable,
                    "detectionSource": detection_source,
                    "status": (
                        "Configured"
                        if configured
                        else (
                            "Configured path missing"
                            if saved_missing
                            else ("Installed" if installed else "Not installed")
                        )
                    ),
                }
            )
        return rows

    def _split_arguments(self, value: str) -> list[str]:
        arguments = shlex.split(value or "", posix=os.name != "nt")
        if os.name != "nt":
            return arguments
        return [
            argument[1:-1]
            if len(argument) >= 2 and argument[0] == argument[-1] and argument[0] in {'"', "'"}
            else argument
            for argument in arguments
        ]

    def _enabled_db_browser(self) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM apps
                WHERE enabled = 1 AND type = 'DB Browser'
                ORDER BY app COLLATE NOCASE
                LIMIT 1;
                """
            ).fetchone()

    def _enabled_ssh_client(self) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM apps
                WHERE enabled = 1 AND type = 'SSH Client'
                ORDER BY app COLLATE NOCASE
                LIMIT 1;
                """
            ).fetchone()

    def _enabled_sftp_client(self) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute(
                """
                SELECT *
                FROM apps
                WHERE enabled = 1 AND type = 'SFTP Client'
                ORDER BY app COLLATE NOCASE
                LIMIT 1;
                """
            ).fetchone()

    @pyqtProperty(bool, notify=toolsChanged)
    def hasEnabledSftpClient(self) -> bool:
        self._ensure_database()
        return self._enabled_sftp_client() is not None

    @pyqtSlot(str, result="QVariantMap")
    def openDeviceCli(self, ip: str) -> dict[str, Any]:
        self._ensure_database()
        ssh_client = self._enabled_ssh_client()
        if ssh_client is None:
            return {
                "ok": False,
                "message": "No active SSH Client configured in External Tools.",
                "settingsKey": "external_tools",
            }

        executable = self._file_url_to_path(str(ssh_client["executable"]))
        if not executable.is_file():
            return {
                "ok": False,
                "message": f"SSH Client executable not found: {executable}",
                "settingsKey": "external_tools",
            }

        args_text = str(ssh_client["arguments"] or "")
        if "{password}" in args_text.casefold():
            return {
                "ok": False,
                "message": "The {password} placeholder is blocked because command-line credentials can be exposed.",
                "settingsKey": "external_tools",
            }
        device = load_device_for_login(ip) or {}
        username = str(device.get("username") or "")

        try:
            arguments = self._split_arguments(args_text)
            has_ip_placeholder = any("{ip}" in argument for argument in arguments)
            
            # Replace placeholders
            arguments = [argument.replace("{ip}", ip).replace("{username}", username) for argument in arguments]
            if not has_ip_placeholder:
                arguments.append(ip)
                
            command = [str(executable), *arguments]
            kwargs: dict[str, Any] = {"cwd": str(APP_DIR)}
            subprocess.Popen(command, **kwargs)
            return {"ok": True, "message": f"Launched {ssh_client['app']} for {ip}."}
        except Exception as exc:
            return {
                "ok": False,
                "message": f"External SSH Client failed: {exc}",
                "settingsKey": "external_tools",
            }

    @pyqtSlot(str, int, str, str, result="QVariantMap")
    def openSftpClient(
        self,
        ip: str,
        port: int,
        username: str,
        remote_path: str,
    ) -> dict[str, Any]:
        """Open the selected external SFTP client without exposing a password."""
        self._ensure_database()
        sftp_client = self._enabled_sftp_client()
        if sftp_client is None:
            return {
                "ok": True,
                "mode": "builtin",
                "message": "Using the built-in SFTP client.",
            }

        executable = self._file_url_to_path(str(sftp_client["executable"]))
        if not executable.is_file():
            return {
                "ok": False,
                "mode": "builtin",
                "message": f"SFTP Client executable not found: {executable}. Opened the built-in client instead.",
                "settingsKey": "external_tools",
            }

        args_text = str(sftp_client["arguments"] or "")
        if "{password}" in args_text.casefold():
            return {
                "ok": False,
                "mode": "builtin",
                "message": "The {password} placeholder is blocked because command-line credentials can be exposed. Opened the built-in client instead.",
                "settingsKey": "external_tools",
            }

        host = str(ip or "").strip()
        user = str(username or "").strip()
        try:
            port_value = int(port)
        except (TypeError, ValueError):
            port_value = 22
        if not 1 <= port_value <= 65535:
            port_value = 22
        path = str(remote_path or "/").strip() or "/"
        if not path.startswith("/"):
            path = "/" + path

        try:
            arguments = self._split_arguments(args_text)
            supported_placeholders = ("{ip}", "{port}", "{username}", "{path}")
            if host:
                replacements = {
                    "{ip}": host,
                    "{port}": str(port_value),
                    "{username}": user,
                    "{path}": path,
                }
                has_ip_placeholder = any(
                    "{ip}" in argument.casefold() for argument in arguments
                )
                for placeholder, value in replacements.items():
                    arguments = [
                        re.sub(re.escape(placeholder), lambda _match, replacement=value: replacement, argument, flags=re.IGNORECASE)
                        for argument in arguments
                    ]
                if not has_ip_placeholder:
                    arguments.append(host)
            else:
                # ActivityBar launches the application's own login/session UI.
                # Omit only target-dependent tokens; keep static launch switches.
                arguments = [
                    argument
                    for argument in arguments
                    if not any(
                        placeholder in argument.casefold()
                        for placeholder in supported_placeholders
                    )
                ]

            command = [str(executable), *arguments]
            subprocess.Popen(command, cwd=str(APP_DIR))
            target = f" for {host}" if host else ""
            return {
                "ok": True,
                "mode": "external",
                "message": f"Launched {sftp_client['app']}{target}.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "mode": "builtin",
                "message": f"External SFTP Client failed: {exc}. Opened the built-in client instead.",
                "settingsKey": "external_tools",
            }

    def _quote_identifier(self, name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    @pyqtSlot(result="QVariant")
    def getToolTypes(self) -> list[str]:
        return list(self.TOOL_TYPES)

    @pyqtSlot(result="QVariant")
    def getTools(self) -> list[dict[str, Any]]:
        self._ensure_database()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, app, type, executable, arguments, enabled, description
                FROM apps
                ORDER BY type COLLATE NOCASE, app COLLATE NOCASE;
                """
            ).fetchall()
        return self._dict_rows(rows)

    @pyqtSlot(str, str, str, str, bool, str, result="QVariant")
    def saveTool(self, app: str, app_type: str, executable: str, arguments: str, enabled: bool, description: str) -> dict[str, Any]:
        app = (app or "").strip()
        app_type = (app_type or "").strip()
        executable = (executable or "").strip()
        if not app:
            return {"ok": False, "message": "App name is required."}
        if app_type not in self.TOOL_TYPES:
            return {"ok": False, "message": "Tool type is invalid."}
        validation = self.validateExecutable(executable)
        if not validation.get("ok"):
            return {"ok": False, "message": str(validation.get("message") or "Executable path is invalid.")}
        executable = str(validation["path"])
        if "{password}" in (arguments or "").casefold():
            return {
                "ok": False,
                "message": "The {password} placeholder is blocked. Use an interactive or key-based authentication flow.",
            }

        try:
            with closing(self._connect()) as conn:
                if enabled:
                    conn.execute(
                        "UPDATE apps SET enabled = 0 WHERE type = ? AND app <> ?;",
                        (app_type, app),
                    )
                conn.execute(
                    """
                    INSERT INTO apps (app, type, executable, arguments, enabled, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(app) DO UPDATE SET
                        type = excluded.type,
                        executable = excluded.executable,
                        arguments = excluded.arguments,
                        enabled = excluded.enabled,
                        description = excluded.description;
                    """,
                    (app, app_type, executable, arguments or "", 1 if enabled else 0, description or ""),
                )
                conn.commit()
            self.toolsChanged.emit()
            return {"ok": True, "message": "External tool saved."}
        except sqlite3.Error as exc:
            return {"ok": False, "message": str(exc)}

    @pyqtSlot(str, result=bool)
    def deleteTool(self, app: str) -> bool:
        try:
            with closing(self._connect()) as conn:
                conn.execute("DELETE FROM apps WHERE app = ?;", ((app or "").strip(),))
                conn.commit()
            self.toolsChanged.emit()
            return True
        except sqlite3.Error:
            return False

    @pyqtSlot(result="QVariant")
    def openDeviceDatabase(self) -> dict[str, Any]:
        self._ensure_database()
        browser = self._enabled_db_browser()
        if browser is None:
            result = self.loadDefaultDatabase()
            return {**result, "mode": "default"}

        executable = self._file_url_to_path(str(browser["executable"]))
        if not executable.is_file():
            self.loadDefaultDatabase()
            return {
                "ok": False,
                "mode": "default",
                "message": f"DB Browser path not found: {executable}",
                "settingsKey": "external_tools",
            }

        args_text = str(browser["arguments"] or "")
        db_text = str(self.device_db_path.resolve())
        try:
            arguments = self._split_arguments(args_text)
            has_database_placeholder = any("{db}" in argument for argument in arguments)
            arguments = [argument.replace("{db}", db_text) for argument in arguments]
            if not has_database_placeholder:
                arguments.append(db_text)
            command = [str(executable), *arguments]
            kwargs: dict[str, Any] = {"cwd": str(APP_DIR)}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(command, **kwargs)
            return {"ok": True, "mode": "external", "message": f"Opened with {browser['app']}."}
        except Exception as exc:
            self.loadDefaultDatabase()
            return {
                "ok": False,
                "mode": "default",
                "message": f"External DB Browser failed: {exc}",
                "settingsKey": "external_tools",
            }

    @pyqtSlot(result="QVariant")
    def loadDefaultDatabase(self) -> dict[str, Any]:
        if not self.device_db_path.exists():
            return {"ok": False, "message": f"Database not found: {self.device_db_path}"}
        tables = self.getDatabaseTables()
        if tables and not self._active_table:
            self._active_table = tables[0]
        self.browserChanged.emit()
        return {"ok": True, "message": "Opened with the built-in DB browser.", "tables": tables}

    @pyqtSlot(result="QVariant")
    def getDatabaseTables(self) -> list[str]:
        if not self.device_db_path.exists():
            return []
        try:
            with closing(sqlite3.connect(self.device_db_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name COLLATE NOCASE;
                    """
                ).fetchall()
        except sqlite3.Error:
            return []
        return [str(row[0]) for row in rows]

    @pyqtSlot(str, result="QVariant")
    def getTableRows(self, table_name: str) -> dict[str, Any]:
        table_name = (table_name or "").strip()
        if table_name not in self.getDatabaseTables():
            return {"ok": False, "message": "Invalid table.", "columns": [], "rows": [], "editable": False}
        table_sql = self._quote_identifier(table_name)
        try:
            with closing(sqlite3.connect(self.device_db_path)) as conn:
                conn.row_factory = sqlite3.Row
                columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_sql});")]
                try:
                    rows = conn.execute(f"SELECT rowid AS __rowid__, * FROM {table_sql} LIMIT 500;").fetchall()
                    editable = True
                except sqlite3.Error:
                    rows = conn.execute(f"SELECT * FROM {table_sql} LIMIT 500;").fetchall()
                    editable = False
        except sqlite3.Error as exc:
            return {"ok": False, "message": str(exc), "columns": [], "rows": [], "editable": False}
        self._active_table = table_name
        self.browserChanged.emit()
        return {
            "ok": True,
            "message": f"Loaded {table_name}",
            "columns": columns,
            "rows": self._dict_rows(rows),
            "editable": editable,
        }

    @pyqtSlot(str, int, str, str, result="QVariant")
    def updateTableCell(self, table_name: str, rowid: int, column_name: str, value: str) -> dict[str, Any]:
        table_name = (table_name or "").strip()
        column_name = (column_name or "").strip()
        if table_name not in self.getDatabaseTables():
            return {"ok": False, "message": "Invalid table."}

        table_sql = self._quote_identifier(table_name)
        try:
            with closing(sqlite3.connect(self.device_db_path)) as conn:
                columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_sql});")]
                if column_name not in columns:
                    return {"ok": False, "message": "Invalid column."}
                conn.execute(
                    f"UPDATE {table_sql} SET {self._quote_identifier(column_name)} = ? WHERE rowid = ?;",
                    (value, rowid),
                )
                conn.commit()
        except sqlite3.Error as exc:
            return {"ok": False, "message": str(exc)}

        self.browserChanged.emit()
        return {"ok": True, "message": f"Updated {table_name}.{column_name}."}

__all__ = ["ExternalToolsManager"]
