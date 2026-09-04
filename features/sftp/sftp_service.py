from __future__ import annotations

import base64
import hashlib
import hmac
import posixpath
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paramiko

from .file_model import FileItem

ProgressCallback = Callable[[int, int], None]


def host_key_fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class UnknownHostKeyError(paramiko.SSHException):
    expected_user_action = True

    def __init__(self, hostname: str, key: paramiko.PKey) -> None:
        self.info = {
            "host": hostname,
            "keyType": key.get_name(),
            "fingerprint": host_key_fingerprint(key),
        }
        super().__init__(f"Host {hostname} is not trusted yet")


class CaptureHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname: str, key: paramiko.PKey) -> None:
        raise UnknownHostKeyError(hostname, key)


class ConfirmedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_fingerprint: str, known_hosts_path: Path) -> None:
        self._expected = expected_fingerprint
        self._known_hosts_path = known_hosts_path

    def missing_host_key(self, client, hostname: str, key: paramiko.PKey) -> None:
        actual = host_key_fingerprint(key)
        if not hmac.compare_digest(actual, self._expected):
            raise paramiko.SSHException(
                "The host key changed during confirmation; connection cancelled"
            )
        client.get_host_keys().add(hostname, key.get_name(), key)
        self._known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
        client.save_host_keys(str(self._known_hosts_path))


@dataclass(slots=True)
class ConnectionOptions:
    host: str
    port: int
    username: str
    password: str = ""
    private_key: str = ""
    timeout: float = 12.0


class SftpService:
    """Paramiko facade used only from a serialized worker queue."""

    def __init__(self) -> None:
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self._pending_host_key: dict[str, str] | None = None

    @property
    def pending_host_key(self) -> dict[str, str] | None:
        return dict(self._pending_host_key) if self._pending_host_key else None

    def connect(self, options: ConnectionOptions, accepted_fingerprint: str = "") -> str:
        self.disconnect()
        self._pending_host_key = None
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        known_hosts_path = Path.home() / ".ssh" / "known_hosts"
        if known_hosts_path.exists():
            ssh.load_host_keys(str(known_hosts_path))
        policy = (
            ConfirmedHostKeyPolicy(accepted_fingerprint, known_hosts_path)
            if accepted_fingerprint
            else CaptureHostKeyPolicy()
        )
        ssh.set_missing_host_key_policy(policy)
        arguments = {
            "hostname": options.host,
            "port": options.port,
            "username": options.username,
            "password": options.password or None,
            "timeout": options.timeout,
            "banner_timeout": options.timeout,
            "auth_timeout": options.timeout,
            "look_for_keys": not bool(options.private_key),
            "allow_agent": True,
        }
        if options.private_key:
            arguments["key_filename"] = options.private_key
        try:
            ssh.connect(**arguments)
        except UnknownHostKeyError as exc:
            self._pending_host_key = exc.info
            ssh.close()
            raise
        try:
            sftp = ssh.open_sftp()
        except Exception:
            ssh.close()
            raise
        self._ssh, self._sftp = ssh, sftp
        return sftp.normalize(".")

    def disconnect(self) -> None:
        if self._sftp is not None:
            try:
                self._sftp.close()
            finally:
                self._sftp = None
        if self._ssh is not None:
            try:
                self._ssh.close()
            finally:
                self._ssh = None

    def list_directory(self, remote_path: str) -> list[FileItem]:
        entries = self._require_sftp().listdir_attr(remote_path)
        items = []
        for entry in entries:
            mode = getattr(entry, "st_mode", 0) or 0
            is_directory = stat.S_ISDIR(mode)
            items.append(
                FileItem(
                    name=entry.filename,
                    path=posixpath.join(remote_path, entry.filename),
                    is_directory=is_directory,
                    size=None if is_directory else getattr(entry, "st_size", None),
                    modified_time=getattr(entry, "st_mtime", 0),
                    permissions=stat.filemode(mode),
                )
            )
        return sorted(items, key=lambda item: (not item.is_directory, item.name.casefold()))

    def normalize(self, path: str) -> str:
        return self._require_sftp().normalize(path)

    def upload(
        self, local_path: str, remote_dir: str, callback: ProgressCallback
    ) -> None:
        source = Path(local_path)
        if not source.exists():
            raise FileNotFoundError(f"Local file not found: {source}")
        sftp = self._require_sftp()
        if source.is_file():
            sftp.put(
                str(source),
                posixpath.join(remote_dir, source.name),
                callback=callback,
                confirm=True,
            )
            return

        files = [
            path
            for path in source.rglob("*")
            if path.is_file() and not path.is_symlink()
        ]
        total = sum(path.stat().st_size for path in files)
        remote_root = posixpath.join(remote_dir, source.name)
        self._ensure_remote_directory(remote_root)
        for directory in (
            path for path in source.rglob("*") if path.is_dir() and not path.is_symlink()
        ):
            relative = directory.relative_to(source).as_posix()
            self._ensure_remote_directory(posixpath.join(remote_root, relative))

        completed = 0
        for path in files:
            relative = path.relative_to(source).as_posix()
            target = posixpath.join(remote_root, relative)
            file_size = path.stat().st_size

            def report(current: int, _file_total: int, base=completed) -> None:
                callback(base + current, total)

            sftp.put(str(path), target, callback=report, confirm=True)
            completed += file_size
        callback(total, total)

    def download(
        self, remote_path: str, local_dir: str, callback: ProgressCallback
    ) -> None:
        sftp = self._require_sftp()
        info = sftp.stat(remote_path)
        destination = Path(local_dir, posixpath.basename(remote_path))
        if not stat.S_ISDIR(info.st_mode):
            destination.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote_path, str(destination), callback=callback)
            return

        directories, files = self._walk_remote_directory(remote_path)
        total = sum(item.st_size for _, item in files)
        destination.mkdir(parents=True, exist_ok=True)
        for directory in directories:
            relative = posixpath.relpath(directory, remote_path)
            if relative != ".":
                destination.joinpath(*relative.split("/")).mkdir(
                    parents=True, exist_ok=True
                )

        completed = 0
        for path, item in files:
            relative = posixpath.relpath(path, remote_path)
            target = destination.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)

            def report(current: int, _file_total: int, base=completed) -> None:
                callback(base + current, total)

            sftp.get(path, str(target), callback=report)
            completed += item.st_size
        callback(total, total)

    def create_directory(self, parent: str, name: str) -> None:
        self._require_sftp().mkdir(posixpath.join(parent, name))

    def rename(self, path: str, new_name: str) -> None:
        self._require_sftp().rename(
            path, posixpath.join(posixpath.dirname(path), new_name)
        )

    def delete(self, path: str, is_directory: bool) -> None:
        if is_directory:
            self._require_sftp().rmdir(path)
        else:
            self._require_sftp().remove(path)

    def _ensure_remote_directory(self, path: str) -> None:
        sftp = self._require_sftp()
        try:
            info = sftp.stat(path)
        except OSError:
            sftp.mkdir(path)
            return
        if not stat.S_ISDIR(info.st_mode):
            raise NotADirectoryError(
                f"Remote path already exists and is not a directory: {path}"
            )

    def _walk_remote_directory(self, root: str):
        sftp = self._require_sftp()
        directories = [root]
        files = []
        pending = [root]
        while pending:
            current = pending.pop()
            for item in sftp.listdir_attr(current):
                path = posixpath.join(current, item.filename)
                if stat.S_ISDIR(item.st_mode):
                    directories.append(path)
                    pending.append(path)
                else:
                    files.append((path, item))
        return directories, files

    def _require_sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise RuntimeError("Not connected to an SFTP server")
        return self._sftp
