"""Thin QML facade for terminal, session, and backup operations."""

from __future__ import annotations

import importlib.util
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.app_paths import APP_DIR
from core.tasks import AsyncTaskCoordinator
from features.devices import (
    DeviceLoginService,
    DeviceRepository,
    DeviceService,
    SaveConfigService,
)
from features.devices.batch_service import DeviceBatchService
from features.devices.connection_service import DeviceConnectionService
from features.devices.running_config_service import RunningConfigService
from features.terminal import ManagedTerminalManager
from infrastructure.network.ping import ping_host
from infrastructure.network.session_registry import DeviceSessionRegistry

NETWORK_TASK_TIMEOUT_SECONDS = 15
RUNTIME_MODULES = (
    "PyQt6", "psutil", "netmiko", "paramiko", "ncclient", "nornir",
    "nornir_netmiko", "requests", "urllib3", "jinja2", "yaml", "pyshark",
    "scapy", "napalm", "dulwich",
)
_default_repository = DeviceRepository()
device_login_service = DeviceLoginService(_default_repository)
device_service = DeviceService(_default_repository)
device_session_registry = DeviceSessionRegistry(device_login_service.load)
InfrastructureSessionRegistry = DeviceSessionRegistry

class TerminalHelper(QObject):
    taskStarted = pyqtSignal(str)
    taskProgress = pyqtSignal(str)
    taskFinished = pyqtSignal(bool, str)
    connectHostFinished = pyqtSignal(str, bool, str)
    deviceSessionFinished = pyqtSignal(str, bool, str)
    deviceSessionClosed = pyqtSignal(str)
    deviceCommandFinished = pyqtSignal(str, str, bool, str, str)
    runningConfigFinished = pyqtSignal(str, bool, str)
    saveConfigFinished = pyqtSignal(str, bool, str)
    manualSyncPreviewFinished = pyqtSignal(str, bool, str, object)
    batchStarted = pyqtSignal(str, str, int)
    hostOperationChanged = pyqtSignal(str, str, str, str, int)
    batchProgress = pyqtSignal(str, int, int, int, int)
    batchFinished = pyqtSignal(str, bool, object)
    sessionStateChanged = pyqtSignal(str, str, str)
    terminalStateChanged = pyqtSignal(str, str)
    terminalError = pyqtSignal(str, str)

    def __init__(
        self,
        parent: QObject | None = None,
        config_backup_service: Any | None = None,
        config_sync_service: Any | None = None,
        task_coordinator: AsyncTaskCoordinator | None = None,
        session_registry: InfrastructureSessionRegistry | None = None,
        injected_device_service: DeviceService | None = None,
        injected_login_service: DeviceLoginService | None = None,
        terminal_manager: Any | None = None,
        bootstrap_report: dict[str, Any] | None = None,
    ) -> None:
        """Initialize task tracking and the versioned config-backup service."""
        super().__init__(parent)
        self._background_tasks: dict[str, dict[str, Any]] = {}
        self._task_coordinator = task_coordinator or AsyncTaskCoordinator(self)
        self._session_registry = session_registry or device_session_registry
        self._device_service = injected_device_service or device_service
        self._device_login_service = injected_login_service or device_login_service
        # The companion terminal process and local IPC listener remain lazy.
        self._terminal_manager = terminal_manager or ManagedTerminalManager(
            self._device_login_service.load,
            self,
        )
        state_signal = getattr(self._terminal_manager, "terminalStateChanged", None)
        if state_signal is not None:
            state_signal.connect(self.terminalStateChanged.emit)
        error_signal = getattr(self._terminal_manager, "terminalError", None)
        if error_signal is not None:
            error_signal.connect(self.terminalError.emit)
        self._bootstrap_report = bootstrap_report or {
            "ok": True,
            "statusText": "SYSTEM READY",
            "message": "Python runtime is ready.",
        }
        if config_backup_service is None:
            from features.config_backup import ConfigBackupService

            config_backup_service = ConfigBackupService(APP_DIR / "backup")
        self._config_backup_service = config_backup_service
        if config_sync_service is None:
            from features.config_sync import ConfigSyncService
            from infrastructure.database.paths import DEVICE_NETWORK_DB

            config_sync_service = ConfigSyncService(
                DEVICE_NETWORK_DB,
                self._device_login_service.repository.get_role,
            )
        self._config_sync_service = config_sync_service
        self._batch_service = DeviceBatchService(max_concurrent_hosts=5)
        self._connection_service = DeviceConnectionService(
            self._device_login_service,
            self._device_service,
            self._session_registry,
            self._commit_and_sync_snapshot,
        )
        self._running_config_service = RunningConfigService(
            self._device_login_service,
            self._session_registry,
            self._commit_and_sync_snapshot,
        )
        self._save_config_service = SaveConfigService(self._session_registry)

    def _commit_and_sync_snapshot(
        self,
        host: str,
        snapshot: dict[str, Any],
        sync_mode: str = "automatic",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Commit first, then apply the role/change-aware router sync policy."""
        running_config = str(snapshot.get("running_config") or "")
        backup_result = self._config_backup_service.save_snapshot(host, running_config)
        if not bool(backup_result.get("ok")):
            return backup_result, {
                "ok": False,
                "attempted": False,
                "skipped": True,
                "reason": "backup-failed",
                "message": "Configuration was not synchronized because its backup failed.",
                "summary": {},
            }
        sync_args = (
            host,
            running_config,
            str(snapshot.get("interface_brief") or ""),
            backup_result,
        )
        switch_state = snapshot.get("switch_state")
        switch_kwargs = (
            {"switch_state": dict(switch_state)}
            if isinstance(switch_state, dict)
            else {}
        )
        if sync_mode == "preview" and hasattr(
            self._config_sync_service, "preview_manual_snapshot"
        ):
            sync_result = self._config_sync_service.preview_manual_snapshot(
                *sync_args, **switch_kwargs
            )
        elif sync_mode in {"safe", "force_device_state"} and hasattr(
            self._config_sync_service, "sync_manual_snapshot"
        ):
            sync_result = self._config_sync_service.sync_manual_snapshot(
                *sync_args, mode=sync_mode, **switch_kwargs
            )
        else:
            sync_result = self._config_sync_service.sync_committed_snapshot(
                *sync_args, **switch_kwargs
            )
        return backup_result, sync_result

    def _start_background_task(
        self,
        task_key: str,
        kind: str,
        host: str,
        start_message: str,
        callback: Any,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if task_key in self._background_tasks:
            message = f"A {kind.replace('-', ' ')} task is already running for {host}."
            self.taskFinished.emit(False, message)
            return False

        self._background_tasks[task_key] = {
            "kind": kind,
            "host": host,
            "metadata": metadata or {},
        }

        started = self._task_coordinator.start(
            task_key,
            start_message,
            callback,
            on_started=self._relay_task_started,
            on_progress=self._relay_task_progress,
            on_finished=self._handle_background_task_finished,
        )
        if not started:
            self._background_tasks.pop(task_key, None)
        return started

    @pyqtSlot(str)
    def _relay_task_started(self, message: str) -> None:
        self.taskStarted.emit(message)

    @pyqtSlot(str)
    def _relay_task_progress(self, message: str) -> None:
        self.taskProgress.emit(message)

    @pyqtSlot(str, bool, str, object)
    def _handle_background_task_finished(self, task_key: str, ok: bool, message: str, result: object) -> None:
        entry = self._background_tasks.pop(task_key, {})
        kind = str(entry.get("kind") or "")
        host = str(entry.get("host") or "")
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}

        if kind == "connect-host":
            self.connectHostFinished.emit(host, ok, message)
        elif kind == "open-session":
            self.deviceSessionFinished.emit(host, ok, message)
        elif kind == "device-command":
            command = str(metadata.get("command") or "")
            output = str(result.get("output") or "") if isinstance(result, dict) else ""
            self.deviceCommandFinished.emit(host, command, ok, message, output)
        elif kind == "running-config":
            self.runningConfigFinished.emit(host, ok, message)
        elif kind == "save-config":
            self.saveConfigFinished.emit(host, ok, message)
        elif kind == "manual-sync-preview":
            sync = result.get("sync", {}) if isinstance(result, dict) else {}
            summary = sync.get("summary", {}) if isinstance(sync, dict) else {}
            self.manualSyncPreviewFinished.emit(host, ok, message, summary)
        elif kind == "device-batch":
            batch_id = str(metadata.get("batchId") or "")
            payload = dict(result) if isinstance(result, dict) else {}
            self.batchFinished.emit(batch_id, bool(payload.get("failed", 1) == 0), payload)

        self.taskFinished.emit(ok, message)

    @pyqtSlot()
    def openTerminal(self) -> None:
        """Compatibility slot; device CLI now requires an explicit inventory host."""
        self.taskFinished.emit(
            False,
            "Select a device before opening CAMS Terminal.",
        )

    @pyqtSlot(str, result="QVariant")
    def openDeviceTerminal(self, host: str) -> dict[str, Any]:
        """Open or focus the external CAMS Terminal for one host."""
        return self._terminal_manager.open(host)

    @pyqtSlot(str, result="QVariant")
    def focusDeviceTerminal(self, host: str) -> dict[str, Any]:
        """Request activation of a managed terminal window."""
        return self._terminal_manager.focus(host)

    @pyqtSlot(str, result="QVariant")
    def closeDeviceTerminal(self, host: str) -> dict[str, Any]:
        """Request a graceful close with a bounded process fallback."""
        return self._terminal_manager.close(host)

    @pyqtSlot(str, result="QVariant")
    def restartDeviceTerminal(self, host: str) -> dict[str, Any]:
        """Replace an existing managed terminal with a fresh session."""
        return self._terminal_manager.restart(host)

    @pyqtSlot(str, result=bool)
    def isDeviceTerminalOpen(self, host: str) -> bool:
        """Return whether a managed terminal process is active."""
        return self._terminal_manager.is_running(host)

    @pyqtSlot(str, result=str)
    def deviceTerminalState(self, host: str) -> str:
        """Return the aggregate terminal state exposed to QML."""
        return self._terminal_manager.state_for_device(host)

    @pyqtSlot(str, result="QVariant")
    def pingHost(self, ip: str) -> dict[str, Any]:
        ip = (ip or "").strip()
        if not ip:
            return {"ok": False, "severity": "warning", "message": "Ping failed: host is empty."}
        result = ping_host(APP_DIR, ip)
        return result

    @pyqtSlot(result="QVariant")
    def ensurePythonLoginDeps(self) -> dict[str, Any]:
        missing = [name for name in RUNTIME_MODULES if importlib.util.find_spec(name) is None]
        if missing:
            return {
                "ok": False,
                "statusText": f"MISSING: {len(missing)}",
                "message": "Missing Python packages: " + ", ".join(missing),
            }
        return dict(self._bootstrap_report)

    @pyqtSlot(str, result="QVariant")
    def openDeviceSession(self, host: str) -> dict[str, Any]:
        result = self._session_registry.open(host)
        state = self._session_registry.get_state(host)
        self.sessionStateChanged.emit(host, state, str(result.get("message") or ""))
        return result

    @pyqtSlot(str, result=bool)
    def openDeviceSessionAsync(self, host: str) -> bool:
        host = (host or "").strip()
        if not host:
            message = "Open session failed: host is empty."
            self.deviceSessionFinished.emit("", False, message)
            self.taskFinished.emit(False, message)
            return False

        task_key = f"open-session:{host}"
        start_message = f"Opening CLI session to {host}..."

        def run_open_session(progress: Any) -> dict[str, Any]:
            progress(f"Connecting to {host} with SSH/Telnet...")
            return self._session_registry.open(host)

        return self._start_background_task(task_key, "open-session", host, start_message, run_open_session)

    @pyqtSlot(str, result="QVariant")
    def closeDeviceSession(self, host: str) -> dict[str, Any]:
        result = self._session_registry.close(host)
        reset_result = self._device_service.reset_to_waiting(host)
        if not bool(reset_result.get("ok")):
            print(f"[app] Error updating device to waiting on close: {reset_result.get('message')}")
            
        self.deviceSessionClosed.emit(host)
        self.sessionStateChanged.emit(host, "closed", str(result.get("message") or ""))
        return result

    @pyqtSlot(str, result=bool)
    def hasDeviceSession(self, host: str) -> bool:
        return self._session_registry.has_session(host)

    @pyqtSlot(str, str, result="QVariant")
    def runDeviceCommand(self, host: str, command: str) -> dict[str, Any]:
        host = (host or "").strip()
        command = (command or "").strip()
        if not host:
            return {"ok": False, "severity": "warning", "message": "Command failed: host is empty.", "output": ""}
        if not command:
            return {"ok": False, "severity": "warning", "message": "Command failed: command is empty.", "output": ""}

        executed = self._session_registry.execute(
            host, lambda connector: connector.send_command(command),
            ensure_open=False,
        )
        if not executed.get("ok"):
            return {**executed, "output": ""}
        output = executed.get("value")
        if output is None:
            return {"ok": False, "severity": "error", "message": f"Command failed for {host}: no output returned.", "output": ""}
        return {"ok": True, "severity": "success", "message": f"Command completed for {host}.", "output": str(output)}

    @pyqtSlot(str, str, result=bool)
    def runDeviceCommandAsync(self, host: str, command: str) -> bool:
        host = (host or "").strip()
        command = (command or "").strip()
        if not host or not command:
            message = "Command failed: host or command is empty."
            self.deviceCommandFinished.emit(host, command, False, message, "")
            self.taskFinished.emit(False, message)
            return False

        task_key = f"device-command:{host}:{command}"
        start_message = f"Running command on {host}: {command}"

        def run_command(progress: Any) -> dict[str, Any]:
            progress(f"Waiting for device response from {host}...")
            return self.runDeviceCommand(host, command)

        return self._start_background_task(
            task_key,
            "device-command",
            host,
            start_message,
            run_command,
            {"command": command},
        )

    @pyqtSlot()
    def closeAllDeviceSessions(self) -> None:
        self._session_registry.close_all()

    def shutdown(self) -> None:
        """Stop background jobs and close reusable device sessions."""
        self._terminal_manager.shutdown()
        self._task_coordinator.shutdown()
        self.closeAllDeviceSessions()

    @pyqtSlot(str, result="QVariant")
    def saveRunningConfigBackup(self, host: str) -> dict[str, Any]:
        return self._save_running_config_backup(host, "automatic")

    @pyqtSlot(str, result="QVariant")
    def manualSync(self, host: str) -> dict[str, Any]:
        """Preview synchronization against a fresh running-config snapshot."""
        return self._save_running_config_backup(host, "preview")

    @pyqtSlot(str, str, result="QVariant")
    def applyManualSync(self, host: str, mode: str) -> dict[str, Any]:
        """Recollect and apply a previously previewed synchronization decision."""
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {"safe", "force_device_state"}:
            return {
                "ok": False,
                "severity": "error",
                "message": "Manual Sync mode must be safe or force_device_state.",
            }
        return self._save_running_config_backup(host, normalized_mode)

    # Compatibility wrappers for automation written before the Manual Sync
    # spelling was corrected. New QML and Python callers use the methods above.
    @pyqtSlot(str, result="QVariant")
    def manualSyncSys(self, host: str) -> dict[str, Any]:
        """Compatibility alias for :meth:`manualSync`."""
        return self.manualSync(host)

    @pyqtSlot(str, str, result="QVariant")
    def applyManualSyncSys(self, host: str, mode: str) -> dict[str, Any]:
        """Compatibility alias for :meth:`applyManualSync`."""
        return self.applyManualSync(host, mode)

    def _save_running_config_backup(
        self, host: str, sync_mode: str
    ) -> dict[str, Any]:
        return self._running_config_service.collect(host, sync_mode)

    @pyqtSlot(str, result=bool)
    def saveRunningConfigBackupAsync(self, host: str) -> bool:
        host = (host or "").strip()
        if not host:
            message = "Get running-config failed: host is empty."
            self.runningConfigFinished.emit("", False, message)
            self.taskFinished.emit(False, message)
            return False

        task_key = f"running-config:{host}"
        start_message = f"Getting running-config from {host}..."

        def run_running_config(progress: Any) -> dict[str, Any]:
            progress(f"Running output rcfg for {host}...")
            result = self.saveRunningConfigBackup(host)
            progress(f"Finished running-config task for {host}.")
            return result

        return self._start_background_task(task_key, "running-config", host, start_message, run_running_config)

    @pyqtSlot(str, result=bool)
    def saveDeviceConfigAsync(self, host: str) -> bool:
        """Persist running-config to startup-config on an active SSH/Telnet session."""
        host = str(host or "").strip()
        if not host:
            message = "Save configuration failed: host is empty."
            self.saveConfigFinished.emit("", False, message)
            self.taskFinished.emit(False, message)
            return False

        def run_save_config(progress: Any) -> dict[str, Any]:
            progress(f"Saving configuration on {host}...")
            return self._save_config_service.save(host)

        return self._start_background_task(
            f"save-config:{host}",
            "save-config",
            host,
            f"Saving running configuration on {host}...",
            run_save_config,
        )

    @pyqtSlot(str, result=bool)
    def manualSyncAsync(self, host: str) -> bool:
        """Start an asynchronous Manual Sync preview for one host."""
        host = (host or "").strip()
        if not host:
            self.runningConfigFinished.emit(host, False, "Manual Sync failed: host is empty.")
            return False
        task_key = f"manual-sys-sync:{host}"
        start_message = f"Manual Sync started for {host}..."

        def run_manual_sync(progress):
            progress(f"Collecting complete running-config from {host}...")
            result = self.manualSync(host)
            progress(f"Manual Sync finished for {host}.")
            return result

        return self._start_background_task(
            task_key,
            "manual-sync-preview",
            host,
            start_message,
            run_manual_sync,
        )

    @pyqtSlot(str, str, result=bool)
    def applyManualSyncAsync(self, host: str, mode: str) -> bool:
        """Apply safe/force mode asynchronously after the preview decision."""
        host = (host or "").strip()
        normalized_mode = str(mode or "").strip().lower()
        if not host or normalized_mode not in {"safe", "force_device_state"}:
            self.runningConfigFinished.emit(
                host, False, "Manual Sync apply request is invalid."
            )
            return False
        task_key = f"manual-sys-apply:{host}:{normalized_mode}"

        def run_apply(progress: Any) -> dict[str, Any]:
            progress(f"Recollecting running-config from {host}...")
            result = self.applyManualSync(host, normalized_mode)
            progress(f"Manual Sync {normalized_mode} finished for {host}.")
            return result

        return self._start_background_task(
            task_key,
            "running-config",
            host,
            f"Applying Manual Sync {normalized_mode} for {host}...",
            run_apply,
        )

    @pyqtSlot(str, result=bool)
    def manualSyncSysAsync(self, host: str) -> bool:
        """Compatibility alias for :meth:`manualSyncAsync`."""
        return self.manualSyncAsync(host)

    @pyqtSlot(str, str, result=bool)
    def applyManualSyncSysAsync(self, host: str, mode: str) -> bool:
        """Compatibility alias for :meth:`applyManualSyncAsync`."""
        return self.applyManualSyncAsync(host, mode)

    @pyqtSlot(str, result="QVariant")
    def connectHostAndSync(self, host: str) -> dict[str, Any]:
        result = self._connection_service.connect_and_sync(host)
        self.sessionStateChanged.emit(
            (host or "").strip(),
            self._session_registry.get_state(host),
            str(result.get("message") or ""),
        )
        return result

    @pyqtSlot(str, result=bool)
    def connectHostAndSyncAsync(self, host: str) -> bool:
        host = (host or "").strip()
        if not host:
            message = "Connect failed: host is empty."
            self.connectHostFinished.emit("", False, message)
            self.taskFinished.emit(False, message)
            return False

        task_key = f"connect:{host}"
        start_message = f"Connecting to {host}..."

        def run_connect(progress: Any) -> dict[str, Any]:
            progress(f"Opening device connection to {host}...")
            result = self.connectHostAndSync(host)
            progress(f"Finished connection task for {host}.")
            return result

        return self._start_background_task(task_key, "connect-host", host, start_message, run_connect)

    @pyqtSlot("QVariant", result="QVariant")
    def connectHostsAndSyncAsync(self, hosts_value: Any) -> dict[str, Any]:
        """Compatibility wrapper for the bounded batch API."""
        if not hasattr(self, "_batch_service"):
            hosts = DeviceBatchService.normalize_hosts(hosts_value)
            accepted = [host for host in hosts if self.connectHostAndSyncAsync(host)]
            rejected = [host for host in hosts if host not in accepted]
            return {
                "ok": bool(accepted) and not rejected,
                "accepted": accepted, "rejected": rejected,
                "message": f"Started {len(accepted)} connect task(s).",
            }
        hosts = self._batch_service.normalize_hosts(hosts_value)
        batch_id = self._start_device_batch("connect", hosts)
        return {
            "ok": bool(batch_id), "accepted": hosts if batch_id else [],
            "rejected": [] if batch_id else hosts, "batchId": batch_id,
            "message": f"Started bounded connect batch for {len(hosts)} host(s).",
        }

    def _start_device_batch(self, operation: str, hosts_value: Any) -> str:
        hosts = self._batch_service.normalize_hosts(hosts_value)
        if not hosts:
            return ""
        workers = {
            "connect": self.connectHostAndSync,
            "running-config": self.saveRunningConfigBackup,
            "disconnect": self.closeDeviceSession,
        }
        worker = workers.get(operation)
        if worker is None:
            return ""
        batch_id = self._batch_service.create_batch()
        self.batchStarted.emit(batch_id, operation, len(hosts))

        def host_changed(host: str, state: str, message: str, value: int) -> None:
            """Relay per-host state and publish committed running snapshots."""
            self.hostOperationChanged.emit(batch_id, host, state, message, value)
            if operation == "running-config" and state in {"success", "error"}:
                self.runningConfigFinished.emit(
                    host, state == "success", message
                )

        def run_batch(progress: Any) -> dict[str, Any]:
            return self._batch_service.run(
                batch_id, operation, hosts, worker,
                host_changed,
                lambda completed, success, failed, total: self.batchProgress.emit(
                    batch_id, completed, success, failed, total
                ),
            )

        accepted = self._start_background_task(
            f"batch:{batch_id}", "device-batch", "", f"Starting {operation} batch...",
            run_batch, {"batchId": batch_id, "operation": operation},
        )
        return batch_id if accepted else ""

    @pyqtSlot("QVariantList", result=str)
    def connectHostsAsync(self, hosts: list[str]) -> str:
        return self._start_device_batch("connect", hosts)

    @pyqtSlot("QVariantList", result=str)
    def getRunningConfigsAsync(self, hosts: list[str]) -> str:
        return self._start_device_batch("running-config", hosts)

    @pyqtSlot("QVariantList", result=str)
    def disconnectHostsAsync(self, hosts: list[str]) -> str:
        return self._start_device_batch("disconnect", hosts)

    @pyqtSlot(str, result=bool)
    def cancelBatch(self, batch_id: str) -> bool:
        return self._batch_service.cancel((batch_id or "").strip())

__all__ = ["TerminalHelper", "device_session_registry"]
