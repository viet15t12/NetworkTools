"""Interactive Paramiko PTY child for legacy network devices."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import select
import signal
import subprocess
import sys
import termios
import tty
from pathlib import Path

import paramiko

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from features.devices import DeviceLoginService, DeviceRepository
from features.devices.ssh_algorithm_repository import get_ssh_algorithm_override
from infrastructure.network.ssh_algorithms import make_transport_factory


KNOWN_HOSTS_PATH = Path.home() / ".ssh" / "known_hosts"


def _terminal_size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size(sys.stdin.fileno())
        return max(1, size.columns), max(1, size.lines)
    except OSError:
        return 80, 24


def _connect(db_path: Path, host: str) -> tuple[paramiko.SSHClient, paramiko.Channel]:
    device = DeviceLoginService(DeviceRepository(db_path)).load(host)
    if device is None:
        raise RuntimeError("Device is no longer available in the active workspace.")

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    override = get_ssh_algorithm_override(db_path, host)
    connect_options: dict[str, object] = {
        "hostname": device["host"],
        "port": int(device["port"]),
        "username": device["username"],
        "password": device["password"],
        "look_for_keys": False,
        "allow_agent": False,
        "timeout": 10,
        "banner_timeout": 15,
        "auth_timeout": 15,
    }
    if override:
        connect_options["transport_factory"] = make_transport_factory(override)
    try:
        client.connect(**connect_options)
    except Exception:
        client.close()
        raise
    columns, lines = _terminal_size()
    channel = client.invoke_shell(term="xterm-256color", width=columns, height=lines)
    channel.settimeout(0.0)
    return client, channel


def _fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _confirm_changed_host_key(exc: paramiko.BadHostKeyException) -> bool:
    """Ask the operator before replacing a known SSH server identity."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            app = QApplication(["networktools-host-key-warning"])
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("SSH Host Key Changed")
        dialog.setText(f"The SSH host key for {exc.hostname} has changed.")
        dialog.setInformativeText(
            "This can happen when a device is rebuilt, its RSA key is regenerated, "
            "or the IP address now belongs to another device.\n\n"
            f"Saved key: {_fingerprint(exc.expected_key)}\n"
            f"Received key: {_fingerprint(exc.key)}\n\n"
            "Continue only if you recognize this change. CAMS will replace "
            "the saved key and continue connecting."
        )
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        continue_button = dialog.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(cancel_button)
        dialog.setEscapeButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() is continue_button
    except Exception as dialog_error:
        print(
            f"CAMS could not display the host-key warning: {dialog_error}",
            file=sys.stderr,
        )
        return False


def _replace_changed_host_key(
    exc: paramiko.BadHostKeyException,
    known_hosts_path: Path = KNOWN_HOSTS_PATH,
) -> None:
    """Replace the confirmed stale entry, retaining ssh-keygen's .old backup."""
    hostname = str(exc.hostname or "")
    if not hostname or any(character.isspace() for character in hostname):
        raise RuntimeError("The SSH host-key entry name is invalid.")
    if not known_hosts_path.is_file():
        raise RuntimeError("The saved SSH host-key file is no longer available.")

    current_keys = paramiko.HostKeys(str(known_hosts_path)).lookup(hostname)
    key_type = exc.expected_key.get_name()
    current_key = current_keys.get(key_type) if current_keys is not None else None
    if current_key is None or current_key.asbytes() != exc.expected_key.asbytes():
        raise RuntimeError(
            "The saved SSH host key changed after the warning was displayed; "
            "connection cancelled."
        )

    result = subprocess.run(
        ["ssh-keygen", "-R", hostname, "-f", str(known_hosts_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            "Could not remove the old SSH host key"
            + (f": {detail}" if detail else ".")
        )

    known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
    encoded_key = exc.key.get_base64()
    line = f"{hostname} {exc.key.get_name()} {encoded_key}\n".encode("ascii")
    descriptor = os.open(
        known_hosts_path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _connect_with_host_key_confirmation(
    db_path: Path,
    host: str,
) -> tuple[paramiko.SSHClient, paramiko.Channel]:
    try:
        return _connect(db_path, host)
    except paramiko.BadHostKeyException as exc:
        if not _confirm_changed_host_key(exc):
            raise RuntimeError("SSH connection cancelled because the host key changed.") from exc
        _replace_changed_host_key(exc)
        return _connect(db_path, host)


def _relay(channel: paramiko.Channel) -> int:
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    previous = termios.tcgetattr(stdin_fd)

    def resize(_signum: int, _frame: object) -> None:
        columns, lines = _terminal_size()
        try:
            channel.resize_pty(width=columns, height=lines)
        except OSError:
            pass

    old_handler = signal.signal(signal.SIGWINCH, resize)
    try:
        tty.setraw(stdin_fd)
        while not channel.closed:
            readable, _, _ = select.select([channel, stdin_fd], [], [], 0.25)
            if channel in readable:
                try:
                    data = channel.recv(65536)
                except BlockingIOError:
                    data = b""
                if data:
                    os.write(stdout_fd, data)
                elif channel.exit_status_ready():
                    break
            if stdin_fd in readable:
                data = os.read(stdin_fd, 65536)
                if not data:
                    break
                channel.sendall(data)
        return channel.recv_exit_status() if channel.exit_status_ready() else 0
    finally:
        signal.signal(signal.SIGWINCH, old_handler)
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, previous)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--host", required=True)
    args = parser.parse_args()
    client: paramiko.SSHClient | None = None
    try:
        client, channel = _connect_with_host_key_confirmation(args.db, args.host)
        return _relay(channel)
    except (OSError, paramiko.SSHException, RuntimeError) as exc:
        print(f"CAMS SSH failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
