from __future__ import annotations

import json
import posixpath
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    QSettings,
    QThreadPool,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)

from .credential_store import DpapiCredentialStore
from .file_model import FileListModel
from .local_service import LocalFileService
from .scp_running_config import ScpRunningConfigService
from .sftp_service import ConnectionOptions, SftpService
from .transfer_model import TransferItem, TransferModel
from .workers import OperationWorker


class TransferCancelled(RuntimeError):
    pass


def valid_entry_name(value: str) -> bool:
    name = str(value or "").strip()
    return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name


class SftpController(QObject):
    """Single QML-facing API; all blocking filesystem/network I/O is off-thread."""

    connectedChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    localPathChanged = pyqtSignal()
    remotePathChanged = pyqtSignal()
    statusMessageChanged = pyqtSignal()
    navigationChanged = pyqtSignal()
    savedConnectionsChanged = pyqtSignal()
    selectedConnectionChanged = pyqtSignal()
    settingsChanged = pyqtSignal()
    errorOccurred = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)
    hostKeyConfirmationRequired = pyqtSignal(str, str, str)
    scpRunningConfigFinished = pyqtSignal(str, bool, str, str)
    _transferProgress = pyqtSignal(str, int, int)

    def __init__(
        self,
        parent: QObject | None = None,
        settings: QSettings | None = None,
        credential_store=None,
        scp_service=None,
        device_login_service=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or QSettings()
        self._credential_store = credential_store or DpapiCredentialStore(self._settings)
        self._auto_save_passwords = (
            self._credential_store.available
            and self._setting_bool(
                self._settings.value("SFTP/autoSavePasswords", False)
            )
        )
        self._local_service = LocalFileService()
        self._sftp_service = SftpService()
        self._scp_service = scp_service or ScpRunningConfigService()
        self._device_login_service = device_login_service
        self._local_model = FileListModel(self)
        self._remote_model = FileListModel(self)
        self._transfer_model = TransferModel(self)
        self._pool = QThreadPool(self)
        # Paramiko SFTPClient is not thread-safe, so remote I/O is serialized.
        self._pool.setMaxThreadCount(1)
        self._pending = 0
        self._connected = False
        self._default_local_path = self._load_default_local_path()
        self._default_remote_path = self._normalize_remote_path(
            self._settings.value("SFTP/defaultRemotePath", "/")
        )
        self._local_path = self._default_local_path
        self._remote_path = "/"
        self._local_history = [self._local_path]
        self._local_history_index = 0
        self._remote_history = [self._remote_path]
        self._remote_history_index = 0
        self._saved_connections = self._load_saved_connections()
        # Rewrite the normalized schema so legacy plaintext password keys cannot
        # survive in the saved-connections JSON.
        self._persist_saved_connections()
        self._selected_connection_id = ""
        self._active_connection_id = ""
        self._status_message = "SFTP disconnected"
        self._cancel_events: dict[str, threading.Event] = {}
        self._pending_connection: ConnectionOptions | None = None
        self._pending_connection_id = ""
        self._pending_initial_remote_path = ""
        self._pending_scp_request: dict | None = None
        self._shutting_down = False
        self._transferProgress.connect(self._on_transfer_progress)
        self.refreshLocal()

    @pyqtProperty(QObject, constant=True)
    def localModel(self) -> QObject:
        return self._local_model

    @pyqtProperty(QObject, constant=True)
    def remoteModel(self) -> QObject:
        return self._remote_model

    @pyqtProperty(QObject, constant=True)
    def transferModel(self) -> QObject:
        return self._transfer_model

    @pyqtProperty(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._pending > 0

    @pyqtProperty(str, notify=localPathChanged)
    def localPath(self) -> str:
        return self._local_path

    @pyqtProperty(str, notify=remotePathChanged)
    def remotePath(self) -> str:
        return self._remote_path

    @pyqtProperty(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @pyqtProperty(bool, notify=navigationChanged)
    def localCanGoBack(self) -> bool:
        return self._local_history_index > 0

    @pyqtProperty(bool, notify=navigationChanged)
    def localCanGoForward(self) -> bool:
        return self._local_history_index < len(self._local_history) - 1

    @pyqtProperty(bool, notify=navigationChanged)
    def remoteCanGoBack(self) -> bool:
        return self._connected and self._remote_history_index > 0

    @pyqtProperty(bool, notify=navigationChanged)
    def remoteCanGoForward(self) -> bool:
        return (
            self._connected
            and self._remote_history_index < len(self._remote_history) - 1
        )

    @pyqtProperty("QVariantList", notify=savedConnectionsChanged)
    def savedConnections(self) -> list[dict]:
        return [dict(profile) for profile in self._saved_connections]

    @pyqtProperty("QVariantMap", notify=selectedConnectionChanged)
    def selectedConnection(self) -> dict:
        profile = self._connection_by_id(self._selected_connection_id)
        return dict(profile) if profile else {}

    @pyqtProperty(bool, notify=settingsChanged)
    def autoSavePasswords(self) -> bool:
        return self._auto_save_passwords

    @pyqtProperty(bool, constant=True)
    def passwordStorageAvailable(self) -> bool:
        return bool(self._credential_store.available)

    @pyqtProperty(str, notify=settingsChanged)
    def defaultLocalPath(self) -> str:
        return self._default_local_path

    @pyqtProperty(str, notify=settingsChanged)
    def defaultRemotePath(self) -> str:
        return self._default_remote_path

    @staticmethod
    def _setting_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}

    def _set_connected(self, value: bool) -> None:
        if self._connected != value:
            self._connected = value
            self.connectedChanged.emit()

    def _set_local_path(self, value: str, *, record_history: bool = True) -> None:
        if self._local_path != value:
            self._local_path = value
            self.localPathChanged.emit()
            if record_history:
                self._push_history("local", value)

    def _set_remote_path(self, value: str, *, record_history: bool = True) -> None:
        if self._remote_path != value:
            self._remote_path = value
            self.remotePathChanged.emit()
            if record_history:
                self._push_history("remote", value)

    def _set_status(self, value: str) -> None:
        if self._status_message != value:
            self._status_message = value
            self.statusMessageChanged.emit()

    def _push_history(self, side: str, path: str) -> None:
        history = self._remote_history if side == "remote" else self._local_history
        index_name = (
            "_remote_history_index" if side == "remote" else "_local_history_index"
        )
        index = getattr(self, index_name)
        if history and history[index] == path:
            return
        del history[index + 1 :]
        history.append(path)
        setattr(self, index_name, len(history) - 1)
        self.navigationChanged.emit()

    def _reset_history(self, side: str, path: str) -> None:
        if side == "remote":
            self._remote_history = [path]
            self._remote_history_index = 0
        else:
            self._local_history = [path]
            self._local_history_index = 0
        self.navigationChanged.emit()

    def _load_default_local_path(self) -> str:
        home = self._local_service.home_path()
        raw = str(self._settings.value("SFTP/defaultLocalPath", home) or home)
        try:
            normalized = self._local_service.normalize(self._url_to_path(raw))
        except Exception:
            return home
        return normalized if Path(normalized).is_dir() else home

    @staticmethod
    def _normalize_remote_path(value) -> str:
        path = str(value or "/").strip().replace("\\", "/")
        if not path:
            return "/"
        if not path.startswith("/"):
            path = "/" + path
        return posixpath.normpath(path)

    def _load_saved_connections(self) -> list[dict]:
        raw = self._settings.value("SFTP/savedConnections", "[]")
        try:
            items = json.loads(str(raw or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(items, list):
            return []
        profiles: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            host = str(item.get("host", "")).strip()
            username = str(item.get("username", "")).strip()
            try:
                port = int(item.get("port", 22))
            except (TypeError, ValueError):
                port = 22
            if not host or not username or not 1 <= port <= 65535:
                continue
            profile_id = str(item.get("id", "")).strip() or uuid.uuid4().hex
            profiles.append({
                "id": profile_id,
                "name": str(item.get("name", "")).strip() or host,
                "host": host,
                "port": port,
                "username": username,
                "keyPath": str(item.get("keyPath", "")),
                "localPath": str(item.get("localPath", "")) or self._default_local_path,
                "remotePath": self._normalize_remote_path(item.get("remotePath", "/")),
                "transferMode": (
                    "scp"
                    if str(item.get("transferMode", "sftp")).casefold() == "scp"
                    else "sftp"
                ),
                "lastConnected": str(item.get("lastConnected", "")),
                "passwordSaved": (
                    self._setting_bool(item.get("passwordSaved", False))
                    and self._credential_store.has(profile_id)
                ),
            })
        return profiles

    def _persist_saved_connections(self) -> None:
        self._settings.setValue(
            "SFTP/savedConnections",
            json.dumps(self._saved_connections, ensure_ascii=False),
        )
        self._settings.sync()

    def _connection_by_id(self, profile_id: str) -> dict | None:
        return next(
            (
                profile
                for profile in self._saved_connections
                if profile["id"] == profile_id
            ),
            None,
        )

    def _find_connection(self, host: str, port: int, username: str) -> dict | None:
        return next(
            (
                profile
                for profile in self._saved_connections
                if profile["host"].casefold() == host.casefold()
                and profile["port"] == port
                and profile["username"].casefold() == username.casefold()
            ),
            None,
        )

    def _remember_active_paths(self) -> None:
        profile = self._connection_by_id(self._active_connection_id)
        if profile is None:
            return
        profile["localPath"] = self._local_path
        profile["remotePath"] = self._remote_path
        self._persist_saved_connections()
        self.savedConnectionsChanged.emit()

    def _start(self, operation: str, function) -> None:
        if self._shutting_down:
            return
        worker = OperationWorker(operation, function)
        worker.signals.completed.connect(self._operation_completed)
        worker.signals.failed.connect(self._operation_failed)
        was_busy = self.busy
        self._pending += 1
        if not was_busy:
            self.busyChanged.emit()
        self._pool.start(worker)

    def _finish_pending(self) -> None:
        was_busy = self.busy
        self._pending = max(0, self._pending - 1)
        if was_busy != self.busy:
            self.busyChanged.emit()

    @pyqtSlot(str, int, str, str, str)
    def connectServer(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        key_url: str,
    ) -> None:
        self._connect_server("", host, port, username, password, key_url)

    @pyqtSlot(str, str, int, str, str, str)
    def connectServerForProfile(
        self,
        profile_id: str,
        host: str,
        port: int,
        username: str,
        password: str,
        key_url: str,
    ) -> None:
        profile = self._connection_by_id(profile_id)
        if (
            not password
            and profile is not None
            and profile.get("passwordSaved", False)
        ):
            password = self._credential_store.read(profile["id"])
        self._connect_server(profile_id, host, port, username, password, key_url)

    def _connect_server(
        self,
        profile_id: str,
        host: str,
        port: int,
        username: str,
        password: str,
        key_url: str,
    ) -> None:
        host, username = host.strip(), username.strip()
        if not host or not username or not 1 <= port <= 65535:
            self._report_error("Host, username, and a valid port are required")
            return
        key_path = self._url_to_path(key_url) if key_url else ""
        options = ConnectionOptions(host, port, username, password, key_path)
        self._pending_connection = options
        profile = self._connection_by_id(profile_id)
        self._pending_connection_id = profile["id"] if profile else ""
        self._pending_initial_remote_path = (
            profile["remotePath"] if profile else self._default_remote_path
        )
        if profile:
            local_path = str(profile.get("localPath", ""))
            try:
                normalized = self._local_service.normalize(local_path)
                if Path(normalized).is_dir():
                    self._set_local_path(normalized)
                    self.refreshLocal()
            except Exception:
                pass
        self._set_status(f"Connecting to {host}:{port}...")
        self.logMessage.emit(self._status_message, "info")
        self._start(
            "connect",
            lambda: (self._sftp_service.connect(options), host, port),
        )

    @pyqtSlot(bool)
    def confirmHostKey(self, accepted: bool) -> None:
        scp_info = self._scp_service.pending_host_key
        scp_request = self._pending_scp_request
        if scp_info and scp_request is not None:
            if not accepted:
                host = scp_request["options"].host
                self._pending_scp_request = None
                self._set_status("SCP download from the untrusted server was cancelled")
                self.logMessage.emit(self._status_message, "warning")
                self.scpRunningConfigFinished.emit(
                    host, False, self._status_message, ""
                )
                return
            self._set_status(
                f"Verifying the host key for {scp_request['options'].host}..."
            )
            self._start_scp_download(scp_info["fingerprint"])
            return
        info = self._sftp_service.pending_host_key
        options = self._pending_connection
        if not accepted or not info or options is None:
            self._pending_connection = None
            self._pending_connection_id = ""
            self._pending_initial_remote_path = ""
            self._set_status("Connection to the untrusted server was cancelled")
            self.logMessage.emit(self._status_message, "warning")
            return
        fingerprint = info["fingerprint"]
        self._set_status(f"Verifying the host key for {options.host}...")
        self._start(
            "connect",
            lambda: (
                self._sftp_service.connect(options, fingerprint),
                options.host,
                options.port,
            ),
        )

    @pyqtSlot()
    def disconnectServer(self) -> None:
        if not self._connected:
            return
        self._set_status("Disconnecting...")
        self._start("disconnect", self._sftp_service.disconnect)

    @pyqtSlot()
    def refreshLocal(self) -> None:
        path = self._local_path
        self._start("local:list", lambda: (path, self._local_service.list_directory(path)))

    @pyqtSlot(str)
    def openLocalDirectory(self, path: str) -> None:
        try:
            normalized = self._local_service.normalize(self._url_to_path(path))
        except Exception as exc:
            self._report_error(str(exc))
            return
        self._set_local_path(normalized)
        self.refreshLocal()

    @pyqtSlot()
    def localGoUp(self) -> None:
        self.openLocalDirectory(self._local_service.parent(self._local_path))

    @pyqtSlot()
    def localGoBack(self) -> None:
        self._navigate_history("local", -1)

    @pyqtSlot()
    def localGoForward(self) -> None:
        self._navigate_history("local", 1)

    @pyqtSlot()
    def refreshRemote(self) -> None:
        if not self._connected:
            return
        path = self._remote_path
        self._start("remote:list", lambda: (path, self._sftp_service.list_directory(path)))

    @pyqtSlot(str)
    def openRemoteDirectory(self, path: str) -> None:
        if self._connected:
            self._start("remote:open", lambda: self._sftp_service.normalize(path))

    @pyqtSlot()
    def remoteGoUp(self) -> None:
        parent = posixpath.dirname(self._remote_path.rstrip("/")) or "/"
        self.openRemoteDirectory(parent)

    @pyqtSlot()
    def remoteGoBack(self) -> None:
        self._navigate_history("remote", -1)

    @pyqtSlot()
    def remoteGoForward(self) -> None:
        self._navigate_history("remote", 1)

    def _navigate_history(self, side: str, delta: int) -> None:
        history = self._remote_history if side == "remote" else self._local_history
        index_name = (
            "_remote_history_index" if side == "remote" else "_local_history_index"
        )
        index = getattr(self, index_name) + delta
        if not 0 <= index < len(history):
            return
        if side == "remote" and not self._connected:
            return
        setattr(self, index_name, index)
        path = history[index]
        if side == "remote":
            self._set_remote_path(path, record_history=False)
            self.refreshRemote()
        else:
            self._set_local_path(path, record_history=False)
            self.refreshLocal()
        self.navigationChanged.emit()

    @pyqtSlot(str)
    def selectSavedConnection(self, profile_id: str) -> None:
        next_id = profile_id if self._connection_by_id(profile_id) else ""
        if self._selected_connection_id == next_id:
            return
        self._selected_connection_id = next_id
        self.selectedConnectionChanged.emit()

    @pyqtSlot(str, str, str, int, str, str, str, str, result=str)
    @pyqtSlot(str, str, str, int, str, str, str, str, str, bool, result=str)
    @pyqtSlot(
        str, str, str, int, str, str, str, str, str, bool, str, result=str
    )
    def saveConnection(
        self,
        profile_id: str,
        name: str,
        host: str,
        port: int,
        username: str,
        key_path: str,
        local_path: str,
        remote_path: str,
        password: str = "",
        save_password: bool = False,
        transfer_mode: str = "sftp",
    ) -> str:
        host = str(host or "").strip()
        username = str(username or "").strip()
        if not host or not username or not 1 <= int(port) <= 65535:
            self._report_error("Host, username, and a valid port are required")
            return ""
        try:
            normalized_local = self._local_service.normalize(
                self._url_to_path(local_path or self._default_local_path)
            )
        except Exception:
            normalized_local = self._default_local_path
        profile = self._connection_by_id(profile_id)
        if profile is None:
            profile = {"id": uuid.uuid4().hex, "lastConnected": ""}
            self._saved_connections.append(profile)
        had_saved_password = bool(profile.get("passwordSaved", False))
        profile.update({
            "name": str(name or "").strip() or host,
            "host": host,
            "port": int(port),
            "username": username,
            "keyPath": self._url_to_path(str(key_path or "")) if key_path else "",
            "localPath": normalized_local,
            "remotePath": self._normalize_remote_path(remote_path),
            "transferMode": (
                "scp" if str(transfer_mode).casefold() == "scp" else "sftp"
            ),
        })
        if save_password:
            if not self._credential_store.available:
                profile["passwordSaved"] = False
                self._report_error(
                    "Secure password storage is unavailable; "
                    "the connection was saved without a password."
                )
            elif password:
                try:
                    self._credential_store.write(profile["id"], password)
                    profile["passwordSaved"] = True
                except (OSError, RuntimeError):
                    profile["passwordSaved"] = False
                    self._report_error(
                        "The password could not be protected; "
                        "the connection was saved without it."
                    )
            else:
                profile["passwordSaved"] = (
                    had_saved_password
                    and self._credential_store.has(profile["id"])
                )
        else:
            if had_saved_password or self._credential_store.has(profile["id"]):
                self._credential_store.delete(profile["id"])
            profile["passwordSaved"] = False
        self._persist_saved_connections()
        self.savedConnectionsChanged.emit()
        if self._selected_connection_id == profile["id"]:
            self.selectedConnectionChanged.emit()
        else:
            self.selectSavedConnection(profile["id"])
        return profile["id"]

    @pyqtSlot(str)
    @pyqtSlot(str, str)
    # NOTE: chuc nang chua phat trien xong, khong tam quan tam nieu viet bao cao
    def getRunningConfigViaScp(
        self, profile_id: str, password_override: str = ""
    ) -> None:
        profile = self._connection_by_id(profile_id)
        if profile is None:
            self._report_error("The selected SCP connection no longer exists")
            return
        password = str(password_override or "")
        if not password and profile.get("passwordSaved", False):
            password = self._credential_store.read(profile["id"])
        self._request_running_config_scp(
            ConnectionOptions(
                profile["host"],
                profile["port"],
                profile["username"],
                password,
                profile.get("keyPath", ""),
            ),
            profile.get("localPath", self._local_path),
            profile_id=profile["id"],
            profile_name=profile["name"],
        )

    @pyqtSlot(str)
    def getRunningConfigViaScpForDevice(self, host: str) -> None:
        host = str(host or "").strip()
        if not host or self._device_login_service is None:
            self._reject_scp_device_request(
                host, "SCP device inventory backend is unavailable"
            )
            return
        device = self._device_login_service.load(host)
        if device is None:
            self._reject_scp_device_request(
                host, f"Device {host} was not found"
            )
            return
        if self._device_login_service.is_dev_device(device):
            self._reject_scp_device_request(
                host, f"{host} is a dev-test host; SCP was not started"
            )
            return
        if str(device.get("method", "")).casefold() != "ssh":
            self._reject_scp_device_request(
                host, "Get running-config via SCP requires an SSH device"
            )
            return
        device_type = str(device.get("device_type", "")).casefold()
        if device_type not in {"cisco_ios", "cisco_xe"}:
            self._reject_scp_device_request(
                host,
                "Get running-config via SCP currently supports Cisco IOS/IOS XE",
            )
            return
        self._request_running_config_scp(
            ConnectionOptions(
                host,
                int(device.get("port") or 22),
                str(device.get("username") or ""),
                str(device.get("password") or ""),
            ),
            self._local_path,
            profile_name=str(device.get("device_name") or host),
        )

    def _reject_scp_device_request(self, host: str, message: str) -> None:
        self._set_status(message)
        self.scpRunningConfigFinished.emit(host, False, message, "")
        self._report_error(message)

    @pyqtSlot(str, int, str, str, str, str)
    def getRunningConfigViaScpDirect(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        key_url: str,
        local_directory: str,
    ) -> None:
        host, username = str(host or "").strip(), str(username or "").strip()
        try:
            normalized_port = int(port)
        except (TypeError, ValueError):
            normalized_port = 0
        if not host or not username or not 1 <= normalized_port <= 65535:
            self._report_error("Host, username, and a valid port are required")
            return
        profile = self._find_connection(host, normalized_port, username)
        if (
            not password
            and profile is not None
            and profile.get("passwordSaved", False)
        ):
            password = self._credential_store.read(profile["id"])
        self._request_running_config_scp(
            ConnectionOptions(
                host,
                normalized_port,
                username,
                str(password or ""),
                self._url_to_path(key_url) if key_url else "",
            ),
            local_directory or self._local_path,
            profile_id=profile["id"] if profile else "",
            profile_name=profile["name"] if profile else host,
        )

    def _request_running_config_scp(
        self,
        options: ConnectionOptions,
        local_directory: str,
        *,
        profile_id: str = "",
        profile_name: str = "",
    ) -> None:
        if self._pending_scp_request is not None:
            self._report_error("An SCP running-config download is already in progress")
            return
        try:
            normalized_local = self._local_service.normalize(
                self._url_to_path(local_directory or self._local_path)
            )
        except Exception as exc:
            self._report_error(str(exc))
            return
        self._pending_scp_request = {
            "options": options,
            "localPath": normalized_local,
            "profileId": profile_id,
            "profileName": profile_name or options.host,
        }
        self._set_status(f"Getting running-config from {options.host} via SCP...")
        self.logMessage.emit(self._status_message, "info")
        self._start_scp_download()

    def _start_scp_download(self, accepted_fingerprint: str = "") -> None:
        request = self._pending_scp_request
        if request is None:
            return
        options = request["options"]
        local_path = request["localPath"]
        self._start(
            "scp:running",
            lambda: self._scp_service.download(
                options,
                local_path,
                accepted_fingerprint,
            ),
        )

    @pyqtSlot(str)
    def deleteSavedConnection(self, profile_id: str) -> None:
        remaining = [
            profile for profile in self._saved_connections if profile["id"] != profile_id
        ]
        if len(remaining) == len(self._saved_connections):
            return
        self._saved_connections = remaining
        if self._selected_connection_id == profile_id:
            self._selected_connection_id = ""
            self.selectedConnectionChanged.emit()
        if self._active_connection_id == profile_id:
            self._active_connection_id = ""
        self._credential_store.delete(profile_id)
        self._persist_saved_connections()
        self.savedConnectionsChanged.emit()

    @pyqtSlot(str, str, result="QVariant")
    def setDefaultPaths(self, local_path: str, remote_path: str):
        try:
            normalized_local = self._local_service.normalize(self._url_to_path(local_path))
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        if not Path(normalized_local).is_dir():
            return {"ok": False, "message": "The default local directory does not exist."}
        normalized_remote = self._normalize_remote_path(remote_path)
        self._default_local_path = normalized_local
        self._default_remote_path = normalized_remote
        self._settings.setValue("SFTP/defaultLocalPath", normalized_local)
        self._settings.setValue("SFTP/defaultRemotePath", normalized_remote)
        self._settings.sync()
        self.settingsChanged.emit()
        return {"ok": True, "message": "SFTP default paths saved."}

    @pyqtSlot()
    def resetDefaultPaths(self) -> None:
        self.setDefaultPaths(self._local_service.home_path(), "/")

    @pyqtSlot(bool, result="QVariant")
    def setAutoSavePasswords(self, enabled: bool):
        enabled = bool(enabled)
        if enabled and not self._credential_store.available:
            return {
                "ok": False,
                "message": "Secure password storage is unavailable on this system.",
            }
        if self._auto_save_passwords != enabled:
            self._auto_save_passwords = enabled
            self._settings.setValue("SFTP/autoSavePasswords", enabled)
            self._settings.sync()
            self.settingsChanged.emit()
        return {
            "ok": True,
            "message": (
                "Automatic password saving enabled (not recommended)."
                if enabled
                else "Automatic password saving disabled."
            ),
        }

    @pyqtSlot(int)
    def uploadFile(self, row: int) -> None:
        item = self._local_model.get(row)
        if self._connected and item:
            self._queue_transfer("upload", item["path"], self._remote_path, item["name"])

    @pyqtSlot(int)
    def downloadFile(self, row: int) -> None:
        item = self._remote_model.get(row)
        if self._connected and item:
            self._queue_transfer(
                "download", item["path"], self._local_path, item["name"]
            )

    @pyqtSlot("QVariant")
    def uploadEntries(self, rows) -> None:
        for row in self._normalize_rows(rows):
            self.uploadFile(row)

    @pyqtSlot("QVariant")
    def downloadEntries(self, rows) -> None:
        for row in self._normalize_rows(rows):
            self.downloadFile(row)

    @staticmethod
    def _normalize_rows(rows) -> list[int]:
        if hasattr(rows, "toVariant"):
            rows = rows.toVariant()
        if not isinstance(rows, (list, tuple)):
            return []
        normalized: list[int] = []
        for value in rows:
            try:
                row = int(value)
            except (TypeError, ValueError):
                continue
            if row >= 0 and row not in normalized:
                normalized.append(row)
        return normalized

    def _queue_transfer(
        self, direction: str, source: str, destination: str, name: str
    ) -> None:
        task_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        self._cancel_events[task_id] = cancel_event
        self._transfer_model.add(TransferItem(task_id, name, direction))

        def progress(current: int, total: int) -> None:
            if cancel_event.is_set():
                raise TransferCancelled("Transfer cancelled")
            self._transferProgress.emit(task_id, current, total)

        def transfer() -> str:
            if cancel_event.is_set():
                raise TransferCancelled("Transfer cancelled")
            if direction == "upload":
                self._sftp_service.upload(source, destination, progress)
            else:
                self._sftp_service.download(source, destination, progress)
            return task_id

        self.logMessage.emit(f"Queued {direction}: {name}", "info")
        self._start(f"transfer:{task_id}:{direction}", transfer)

    @pyqtSlot(str)
    def cancelTransfer(self, task_id: str) -> None:
        event = self._cancel_events.get(task_id)
        if event is not None:
            event.set()
            self._transfer_model.update(task_id, status="Cancelling")

    @pyqtSlot(bool, str)
    def createDirectory(self, remote: bool, name: str) -> None:
        if not valid_entry_name(name):
            self._report_error("Invalid folder name")
            return
        clean_name = name.strip()
        if remote:
            if self._connected:
                self._start(
                    "remote:mutate",
                    lambda: self._sftp_service.create_directory(
                        self._remote_path, clean_name
                    ),
                )
        else:
            self._start(
                "local:mutate",
                lambda: self._local_service.create_directory(
                    self._local_path, clean_name
                ),
            )

    @pyqtSlot(bool, int, str)
    def renameEntry(self, remote: bool, row: int, new_name: str) -> None:
        model = self._remote_model if remote else self._local_model
        item = model.get(row)
        if not item:
            return
        if not valid_entry_name(new_name):
            self._report_error("Invalid entry name")
            return
        clean_name = new_name.strip()
        if remote:
            self._start(
                "remote:mutate",
                lambda: self._sftp_service.rename(item["path"], clean_name),
            )
        else:
            self._start(
                "local:mutate",
                lambda: self._local_service.rename(item["path"], clean_name),
            )

    @pyqtSlot(bool, int)
    def deleteEntry(self, remote: bool, row: int) -> None:
        model = self._remote_model if remote else self._local_model
        item = model.get(row)
        if not item:
            return
        if remote:
            self._start(
                "remote:mutate",
                lambda: self._sftp_service.delete(
                    item["path"], item["isDirectory"]
                ),
            )
        else:
            self._start(
                "local:mutate",
                lambda: self._local_service.delete(item["path"]),
            )

    @pyqtSlot(bool, "QVariant")
    def deleteEntries(self, remote: bool, rows) -> None:
        for row in self._normalize_rows(rows):
            self.deleteEntry(remote, row)

    @pyqtSlot(str, object)
    def _operation_completed(self, operation: str, result) -> None:
        self._finish_pending()
        if self._shutting_down:
            return
        if operation == "connect":
            path, host, port = result
            options = self._pending_connection
            profile_id = self._pending_connection_id
            initial_remote_path = self._pending_initial_remote_path
            self._pending_connection = None
            self._pending_connection_id = ""
            self._pending_initial_remote_path = ""
            self._set_connected(True)
            self._set_remote_path(path, record_history=False)
            self._reset_history("remote", path)
            if options is not None:
                profile = self._connection_by_id(profile_id)
                if profile is None:
                    profile = self._find_connection(
                        options.host, options.port, options.username
                    )
                save_password = bool(options.password) and (
                    self._auto_save_passwords
                    or bool(profile and profile.get("passwordSaved", False))
                )
                saved_id = self.saveConnection(
                    profile["id"] if profile else "",
                    profile["name"] if profile else options.host,
                    options.host,
                    options.port,
                    options.username,
                    options.private_key,
                    self._local_path,
                    initial_remote_path or path,
                    options.password if save_password else "",
                    save_password,
                    profile.get("transferMode", "sftp") if profile else "sftp",
                )
                saved = self._connection_by_id(saved_id)
                if saved is not None:
                    saved["lastConnected"] = datetime.now(timezone.utc).isoformat()
                    self._persist_saved_connections()
                    self.savedConnectionsChanged.emit()
                self._active_connection_id = saved_id
            self._set_status(f"Connected to {host}:{port}")
            self.logMessage.emit(self._status_message, "success")
            if initial_remote_path and self._normalize_remote_path(initial_remote_path) != path:
                self.openRemoteDirectory(initial_remote_path)
            else:
                self.refreshRemote()
        elif operation == "scp:running":
            request = self._pending_scp_request or {}
            self._pending_scp_request = None
            request_options = request.get("options")
            host = str(
                result.get("host", "")
                or getattr(request_options, "host", "")
            )
            local_path = str(result.get("localPath", ""))
            profile = self._connection_by_id(str(request.get("profileId", "")))
            if profile is None and request_options is not None:
                profile = self._find_connection(
                    request_options.host,
                    request_options.port,
                    request_options.username,
                )
                save_password = bool(request_options.password) and self._auto_save_passwords
                saved_id = self.saveConnection(
                    profile["id"] if profile else "",
                    str(request.get("profileName", host)),
                    request_options.host,
                    request_options.port,
                    request_options.username,
                    request_options.private_key,
                    str(request.get("localPath", self._local_path)),
                    profile.get("remotePath", "/") if profile else "/",
                    request_options.password if save_password else "",
                    save_password,
                    "scp",
                )
                profile = self._connection_by_id(saved_id)
            if profile is not None:
                profile["transferMode"] = "scp"
                profile["lastConnected"] = datetime.now(timezone.utc).isoformat()
                self._persist_saved_connections()
                self.savedConnectionsChanged.emit()
            message = str(result.get("message", "Running-config downloaded via SCP"))
            self._set_status(message)
            self.logMessage.emit(message, "success")
            if local_path and Path(local_path).parent == Path(self._local_path):
                self.refreshLocal()
            self.scpRunningConfigFinished.emit(host, True, message, local_path)
        elif operation == "disconnect":
            self._remember_active_paths()
            self._active_connection_id = ""
            self._set_connected(False)
            self._remote_model.clear()
            self._set_status("SFTP disconnected")
            self.logMessage.emit(self._status_message, "info")
        elif operation == "local:list":
            if result[0] == self._local_path:
                self._local_model.set_items(result[1])
        elif operation == "remote:list":
            if result[0] == self._remote_path:
                self._remote_model.set_items(result[1])
        elif operation == "remote:open":
            self._set_remote_path(result)
            self.refreshRemote()
        elif operation.startswith("transfer:"):
            task_id = result
            self._cancel_events.pop(task_id, None)
            self._transfer_model.update(task_id, status="Completed")
            self.logMessage.emit("File transfer completed", "success")
            self.refreshLocal()
            self.refreshRemote()
        elif operation == "local:mutate":
            self.refreshLocal()
        elif operation == "remote:mutate":
            self.refreshRemote()

    @pyqtSlot(str, str)
    def _operation_failed(self, operation: str, message: str) -> None:
        self._finish_pending()
        if self._shutting_down:
            return
        if operation == "connect":
            self._set_connected(False)
            self._remote_model.clear()
            host_key = self._sftp_service.pending_host_key
            if host_key and self._pending_connection is not None:
                self._set_status("Waiting for SSH host key confirmation")
                self.logMessage.emit(self._status_message, "warning")
                self.hostKeyConfirmationRequired.emit(
                    host_key["host"],
                    host_key["keyType"],
                    host_key["fingerprint"],
                )
                return
            self._pending_connection = None
            self._pending_connection_id = ""
            self._pending_initial_remote_path = ""
            self._set_status("SFTP connection failed")
        elif operation == "scp:running":
            host_key = self._scp_service.pending_host_key
            request = self._pending_scp_request
            if host_key and request is not None:
                self._set_status("Waiting for SSH host key confirmation")
                self.logMessage.emit(self._status_message, "warning")
                self.hostKeyConfirmationRequired.emit(
                    host_key["host"],
                    host_key["keyType"],
                    host_key["fingerprint"],
                )
                return
            host = request["options"].host if request is not None else ""
            self._pending_scp_request = None
            self._set_status(f"SCP running-config download failed for {host}")
            self.scpRunningConfigFinished.emit(host, False, message, "")
        if operation.startswith("transfer:"):
            task_id = operation.split(":")[1]
            self._cancel_events.pop(task_id, None)
            status = "Cancelled" if "cancel" in message.lower() else "Error"
            self._transfer_model.update(task_id, status=status)
        self._report_error(message)

    @pyqtSlot(str, int, int)
    def _on_transfer_progress(self, task_id: str, current: int, total: int) -> None:
        self._transfer_model.update(
            task_id,
            current=current,
            total=total,
            status="Transferring",
        )

    def _report_error(self, message: str) -> None:
        self.errorOccurred.emit(message)
        self.logMessage.emit(message, "error")

    @staticmethod
    def _url_to_path(value: str) -> str:
        if value.startswith("file:"):
            return QUrl(value).toLocalFile()
        return str(Path(value).expanduser())

    @pyqtSlot()
    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._remember_active_paths()
        self._shutting_down = True
        for event in self._cancel_events.values():
            event.set()
        self._pool.clear()
        # Abort blocking SSH/SFTP calls first; only then allow a short worker grace period.
        self._sftp_service.disconnect()
        self._pool.waitForDone(1000)
        self._set_connected(False)
