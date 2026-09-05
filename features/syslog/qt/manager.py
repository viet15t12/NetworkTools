"""Thin Qt/QML adapter over the framework-independent Syslog service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from infrastructure.database.paths import DEVICE_NETWORK_DB, INFO_COLLECTED_DB

from ..application.log_data import SyslogLogDataService
from ..application.server_service import SyslogServerService
from ..export import export_logs_xlsx, file_url_to_path
from ..group_service import SyslogGroupService
from ..native import NativeSyslogCollector
from ..smart_filter import SmartFilterError, build_log_filters
from .settings import SyslogSettings


def _variant_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    to_variant = getattr(value, "toVariant", None)
    if callable(to_variant):
        value = to_variant()
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("Syslog data must be a QML object or mapping") from exc


def _variant_list(value: Any) -> list[Any]:
    if value is None:
        return []
    to_variant = getattr(value, "toVariant", None)
    if callable(to_variant):
        value = to_variant()
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    raise TypeError("Syslog rows must be a QML array or list")


class SyslogManager(QObject):
    stateChanged = pyqtSignal()
    messagesInserted = pyqtSignal("QVariant")
    connectedDevicesChanged = pyqtSignal("QVariant")
    queryFinished = pyqtSignal(str, "QVariant", bool)
    deviceConfigStarted = pyqtSignal(str, str)
    deviceConfigFinished = pyqtSignal(str, str, bool, str)
    sourceInterfaceRequired = pyqtSignal(str, str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = SyslogSettings(self)
        self.service = SyslogServerService(
            INFO_COLLECTED_DB, DEVICE_NETWORK_DB,
            self._messages_stored, self._error, self._receiver_error,
        )
        self.native = NativeSyslogCollector(self)
        self.native.messageInserted.connect(self._native_message_stored)
        self.native.collectorError.connect(self._receiver_error)
        self.native.stopped.connect(self._native_stopped)
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="syslog-task")
        self._state_lock = threading.RLock()
        self._count_lock = threading.Lock()
        self._shutdown = False
        self._state = "stopped"
        self._status_message = "Syslog server is stopped."
        self._received_count = 0

    # Compatibility accessors for integrations that used the former facade internals.
    @property
    def repository(self):
        return self.service.repository

    @property
    def configurator(self):
        return self.service.configurator

    @property
    def writer(self):
        return self.service.writer

    @property
    def pipeline(self):
        return self.service.pipeline

    @property
    def receiver(self) -> object | None:
        return self.service.receiver

    def set_database_paths(self, info_db: Any, device_db: Any) -> None:
        was_running = self.listenerState in {"starting", "listening"}
        if was_running:
            self.stopServer()
        self.service.set_database_paths(info_db, device_db)
        if was_running:
            self.startServer()

    @pyqtProperty(str, notify=stateChanged)
    def listenerState(self) -> str:
        with self._state_lock:
            return self._state

    @pyqtProperty(str, notify=stateChanged)
    def statusMessage(self) -> str:
        with self._state_lock:
            return self._status_message

    @pyqtProperty(int, notify=stateChanged)
    def receivedCount(self) -> int:
        with self._count_lock:
            return self._received_count

    @pyqtProperty(int, notify=stateChanged)
    def droppedCount(self) -> int:
        return self.service.dropped

    def _set_state(self, state: str, message: str) -> None:
        with self._state_lock:
            self._state = state
            self._status_message = message
        self.stateChanged.emit()

    @pyqtSlot(result="QVariant")
    def startServer(self) -> dict[str, object]:
        if self._shutdown:
            return {"ok": False, "message": "Syslog manager is shutting down."}
        if self.listenerState in {"starting", "listening"}:
            return {"ok": True, "message": self.statusMessage}
        try:
            config = self.settings.listener_config()
            self._set_state("starting", "Starting Syslog server...")
            # The legacy C++ collector links plain libsqlite3. Keep ingestion in
            # the Python pipeline so every write passes through SQLCipher.
            self.service.start(config, self.settings.retentionDays)
            transports = "UDP+TCP" if config.protocol == "both" else config.protocol.upper()
            message = f"Listening on {config.bind_ip}:{config.port}/{transports}"
            self._set_state("listening", message)
            return {"ok": True, "message": message}
        except Exception as exc:
            self.service.stop()
            self._set_state("error", str(exc))
            return {"ok": False, "message": str(exc)}

    @pyqtSlot(result="QVariant")
    def stopServer(self) -> dict[str, object]:
        if self.listenerState == "stopped":
            return {"ok": True, "message": self.statusMessage}
        self._set_state("stopping", "Stopping Syslog server...")
        self.service.stop()
        self._set_state("stopped", "Syslog server is stopped.")
        return {"ok": True, "message": self.statusMessage}

    def _messages_stored(self, rows: list[dict[str, Any]]) -> None:
        with self._count_lock:
            self._received_count += len(rows)
        self.messagesInserted.emit(rows)
        self.stateChanged.emit()

    def _native_message_stored(self, row: dict[str, Any]) -> None:
        self._messages_stored([dict(row)])

    def _native_stopped(self) -> None:
        if not self._shutdown and self.listenerState not in {"stopped", "stopping", "error"}:
            self._set_state("error", "Native Syslog collector stopped unexpectedly.")

    def _receiver_error(self, message: str) -> None:
        self._set_state("error", message)
        self.errorOccurred.emit(message)
        if not self._shutdown:
            try:
                self.executor.submit(self.service.stop)
            except RuntimeError:
                pass

    def _error(self, message: str) -> None:
        self.errorOccurred.emit(message)
        self.stateChanged.emit()

    @pyqtSlot()
    def loadConnectedDevices(self) -> None:
        def task() -> None:
            try:
                validation = self.settings.validate()
                config = self.settings.listener_config() if validation["ok"] else None
                self.connectedDevicesChanged.emit(self.service.connected_devices(config))
            except Exception as exc:
                self._error(str(exc))
        self.executor.submit(task)

    @pyqtSlot(str)
    def configureDevice(self, host: str) -> None:
        self._device_action(host, "configure")

    @pyqtSlot(str, str)
    def configureDeviceWithInterface(self, host: str, source_interface: str) -> None:
        self._device_action(host, "configure", source_interface)

    @pyqtSlot(str)
    def cancelDevice(self, host: str) -> None:
        self._device_action(host, "cancel")

    @pyqtSlot(str, result="QVariant")
    def getDeviceConfigurations(self, host: str) -> list[dict[str, Any]]:
        """Return every managed Syslog destination for one router or switch."""
        try:
            return self.repository.device_configurations(host)
        except Exception as exc:
            self._error(str(exc))
            return []

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveDeviceConfiguration(self, host: str, payload: Any) -> dict[str, Any]:
        """Persist desired Syslog state without opening a device session."""
        try:
            return self.repository.save_configuration(host, _variant_dict(payload))
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @pyqtSlot(str, "QVariant", result="QVariant")
    def deleteDeviceConfiguration(self, host: str, payload: Any) -> dict[str, Any]:
        """Delete an unapplied row or stage a configured destination for removal."""
        try:
            return self.repository.stage_delete_configuration(
                host, _variant_dict(payload)
            )
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @pyqtSlot(result="QVariant")
    def getSyslogGroupOptions(self) -> dict[str, Any]:
        """Return eligible hosts plus practical defaults from listener settings."""
        try:
            result = SyslogGroupService(self.repository).options()
            result["defaults"] = {
                "server_ip": self.settings.advertisedIp,
                "protocol": "udp",
                "port": self.settings.port,
                "trap_severity": 5,
                "timestamps": True,
                "sequence_numbers": True,
            }
            return result
        except Exception as exc:
            return {"ok": False, "hosts": [], "defaults": {}, "message": str(exc)}

    @pyqtSlot("QVariant", "QVariant", result="QVariant")
    def saveSyslogGroup(self, targets: Any, common: Any) -> dict[str, Any]:
        """Stage one shared Syslog destination for several selected devices."""
        try:
            normalized = [_variant_dict(row) for row in _variant_list(targets)]
            return SyslogGroupService(self.repository).save(
                normalized, _variant_dict(common)
            )
        except Exception as exc:
            return {
                "ok": False,
                "partial": False,
                "successful": [],
                "failed": [],
                "message": str(exc),
            }

    def _device_action(self, host: str, action: str, source_interface: str = "") -> None:
        host = host.strip()
        if not host:
            return
        self.deviceConfigStarted.emit(host, action)

        def task() -> None:
            try:
                validation = self.settings.validate()
                if not validation["ok"]:
                    result = {"ok": False, "message": str(validation["message"])}
                else:
                    config = self.settings.listener_config()
                    if action == "configure" and self.listenerState != "listening":
                        result = {"ok": False, "message": "Start the Syslog listener before configuring a device."}
                    elif action == "configure":
                        result = self.service.configure_device(host, config, source_interface)
                    else:
                        result = self.service.cancel_device(host, config)
            except Exception as exc:
                result = {"ok": False, "message": str(exc)}
            if result.get("code") == "source_interface_required":
                self.sourceInterfaceRequired.emit(host, str(result["message"]))
            else:
                self.deviceConfigFinished.emit(
                    host, action, bool(result["ok"]), str(result["message"])
                )
            self.loadConnectedDevices()
        self.executor.submit(task)

    @pyqtSlot(str, "QVariant", int, int)
    def queryMessages(
        self, request_id: str, filters: Any, before_id: int = 0, limit: int = 200,
    ) -> None:
        data = _variant_dict(filters)

        def task() -> None:
            try:
                rows = self.service.query_messages(data, before_id, limit + 1)
                self.queryFinished.emit(request_id, rows[:limit], len(rows) > limit)
            except Exception as exc:
                self._error(str(exc))
                self.queryFinished.emit(request_id, [], False)
        self.executor.submit(task)

    @pyqtSlot("QVariant", str, result="QVariant")
    def buildLogFilters(self, filters: Any, expression: str) -> dict[str, Any]:
        try:
            return {
                "ok": True,
                "message": "",
                "filters": build_log_filters(_variant_dict(filters), expression),
            }
        except (SmartFilterError, TypeError, ValueError) as exc:
            return {"ok": False, "message": str(exc), "filters": {}}

    @pyqtSlot(result="QVariant")
    def getLogHosts(self) -> list[str]:
        try:
            return self.repository.distinct_hosts()
        except Exception as exc:
            self._error(str(exc))
            return []

    @pyqtSlot(result="QVariant")
    def getLogResetOptions(self) -> dict[str, Any]:
        """Return reset scopes and counts for the Settings safety UI."""
        try:
            return SyslogLogDataService(self.repository).options()
        except Exception as exc:
            return {"ok": False, "total": 0, "options": [], "message": str(exc)}

    @pyqtSlot(str, str, result="QVariant")
    def exportLogResetScope(self, file_url: str, host: str) -> dict[str, Any]:
        """Export every message in a prospective reset scope."""
        try:
            return SyslogLogDataService(self.repository).export_scope(
                file_url_to_path(file_url), host
            )
        except Exception as exc:
            return {"ok": False, "message": f"Could not export Syslog Excel file: {exc}"}

    @pyqtSlot(str, str, result="QVariant")
    def resetLogData(self, host: str, confirmation: str) -> dict[str, Any]:
        """Reset a host/all logs only after an exact typed confirmation."""
        selected_host = str(host or "").strip()
        log_data = SyslogLogDataService(self.repository)
        if not log_data.is_authorized(selected_host, confirmation):
            return log_data.reset(selected_host, confirmation)

        was_running = self.listenerState in {"starting", "listening"}
        if was_running:
            stopped = self.stopServer()
            if not stopped.get("ok"):
                return {
                    "ok": False,
                    "deleted": 0,
                    "message": str(
                        stopped.get("message") or "Could not stop the listener."
                    ),
                }
        try:
            result = log_data.reset(selected_host, confirmation)
        except Exception as exc:
            restart = self.startServer() if was_running else {"ok": True}
            suffix = (
                ""
                if restart.get("ok")
                else f" Listener restart also failed: {restart.get('message')}"
            )
            return {
                "ok": False,
                "deleted": 0,
                "message": f"Could not reset Syslog data: {exc}{suffix}",
            }

        restart = self.startServer() if was_running else {"ok": True}
        message = str(result["message"])
        if not restart.get("ok"):
            message += f" Listener restart failed: {restart.get('message')}"
        return {
            "ok": True,
            "deleted": int(result["deleted"]),
            "listenerRestarted": bool(restart.get("ok")),
            "message": message,
        }

    @pyqtSlot(str, "QVariant", "QVariant", result="QVariant")
    def exportCurrentMessages(
        self, file_url: str, rows: Any, filters: Any,
    ) -> dict[str, Any]:
        try:
            values = [_variant_dict(row) for row in _variant_list(rows)]
            if not values:
                return {"ok": False, "message": "There are no displayed logs to export."}
            target = export_logs_xlsx(
                file_url_to_path(file_url), values, _variant_dict(filters)
            )
            return {
                "ok": True,
                "message": f"Exported {len(values)} displayed logs to {target}",
                "path": str(target),
                "count": len(values),
            }
        except Exception as exc:
            return {"ok": False, "message": f"Could not export Syslog Excel file: {exc}"}

    @pyqtSlot()
    def shutdown(self) -> None:
        self._shutdown = True
        self.native.stop()
        self.service.stop(receiver_timeout=0.5, writer_timeout=1.0)
        self.executor.shutdown(wait=True, cancel_futures=True)


__all__ = [
    "SyslogManager",
    "_variant_dict",
    "_variant_list",
]
