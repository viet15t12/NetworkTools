"""Qt monitoring facade backed by infrastructure system probes."""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal

from infrastructure.system.network_info import read_network_info
from infrastructure.system.resource_monitor import read_ram_usage_percent
from infrastructure.system.virtual_lab import VirtualLabInfo, VirtualLabProbe

if TYPE_CHECKING:
    from .settings import StatusBarSettings

class NetworkMonitor(QObject):
    networkChanged = pyqtSignal()
    systemInfoChanged = pyqtSignal()

    def __init__(
        self,
        parent: QObject | None = None,
        settings: StatusBarSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._connected = False
        self._connection_type = "none"
        self._network_name = ""
        self._virtual_lab_name = ""
        self._virtual_lab = VirtualLabInfo()
        self._virtual_labs: tuple[VirtualLabInfo, ...] = ()
        self._virtual_probe = VirtualLabProbe()
        self._virtual_future: Future[tuple[VirtualLabInfo, ...]] | None = None
        self._virtual_executor: ThreadPoolExecutor | None = None
        self._virtual_probe_enabled = os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
        self._ram_usage_percent = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)
        if settings is not None:
            settings.settingsChanged.connect(self._request_virtual_refresh)
        self._refresh()

    def _virtual_credentials(self) -> tuple[str, str, str]:
        if self._settings is None:
            return "", "", ""
        return (
            self._settings.virtualLabServerUrl,
            self._settings.virtualLabUsername,
            self._settings.virtualLabPassword,
        )

    def _request_virtual_refresh(self) -> None:
        self._start_virtual_probe()

    def _start_virtual_probe(self) -> None:
        if not self._virtual_probe_enabled or self._virtual_future is not None:
            return
        if self._virtual_executor is None:
            self._virtual_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="virtual-lab")
        self._virtual_probe.reset_cancellation()
        self._virtual_future = self._virtual_executor.submit(
            self._virtual_probe.inspect_all,
            *self._virtual_credentials(),
        )

    def _apply_virtual_labs(self, infos: tuple[VirtualLabInfo, ...]) -> None:
        if infos == self._virtual_labs:
            return
        self._virtual_labs = infos
        if infos:
            priority = {"active": 0, "idle": 1, "online": 2, "starting": 3}
            self._virtual_lab = min(infos, key=lambda item: priority.get(item.state, 9))
            detail = (
                self._virtual_lab.lab_name
                or self._virtual_lab.server_ip
                or self._virtual_lab.adapter_name
            )
            self._virtual_lab_name = (
                f"{self._virtual_lab.platform} · {detail}"
                if detail
                else self._virtual_lab.platform
            )
        else:
            self._virtual_lab = VirtualLabInfo()
            self._virtual_lab_name = ""
        self.networkChanged.emit()

    def _refresh(self) -> None:
        ram_usage_percent = read_ram_usage_percent()
        if ram_usage_percent != self._ram_usage_percent:
            self._ram_usage_percent = ram_usage_percent
            self.systemInfoChanged.emit()

        connected, connection_type, network_name, _adapter_lab_name = read_network_info()
        if (
            connected != self._connected
            or connection_type != self._connection_type
            or network_name != self._network_name
        ):
            self._connected = connected
            self._connection_type = connection_type
            self._network_name = network_name
            self.networkChanged.emit()

        if self._virtual_future is not None and self._virtual_future.done():
            future = self._virtual_future
            self._virtual_future = None
            try:
                self._apply_virtual_labs(future.result())
            except Exception:
                self._apply_virtual_labs(())
        self._start_virtual_probe()

    def shutdown(self) -> None:
        """Stop periodic probes before application teardown begins."""
        self._timer.stop()
        if self._settings is not None:
            try:
                self._settings.settingsChanged.disconnect(self._request_virtual_refresh)
            except TypeError:
                pass
        self._virtual_probe.cancel()
        if self._virtual_future is not None:
            self._virtual_future.cancel()
            self._virtual_future = None
        if self._virtual_executor is not None:
            # ``wait=False`` still leaves ThreadPoolExecutor workers registered
            # with Python's atexit hook, which then blocks in threading.join()
            # and prints a KeyboardInterrupt traceback when the app is closed
            # from a terminal. Probe operations are timeout-bounded, so finish
            # the active worker here while Qt objects are still alive.
            self._virtual_executor.shutdown(wait=True, cancel_futures=True)
            self._virtual_executor = None

    @pyqtProperty(bool, notify=networkChanged)
    def isConnected(self) -> bool:
        return self._connected

    @pyqtProperty(str, notify=networkChanged)
    def connectionType(self) -> str:
        return self._connection_type

    @pyqtProperty(str, notify=networkChanged)
    def networkName(self) -> str:
        return self._network_name

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabName(self) -> str:
        return self._virtual_lab_name

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabState(self) -> str:
        return self._virtual_lab.state

    @pyqtProperty(bool, notify=networkChanged)
    def virtualLabActive(self) -> bool:
        return self._virtual_lab.is_active

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabPlatform(self) -> str:
        return self._virtual_lab.platform

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabServerIp(self) -> str:
        return self._virtual_lab.server_ip

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabUrl(self) -> str:
        return self._virtual_lab.server_url

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabNameDetected(self) -> str:
        return self._virtual_lab.lab_name

    @pyqtProperty(str, notify=networkChanged)
    def virtualLabDetail(self) -> str:
        return self._virtual_lab.detail

    @pyqtProperty(int, notify=networkChanged)
    def virtualLabRunningNodeCount(self) -> int:
        return self._virtual_lab.running_node_count

    @pyqtProperty(list, notify=networkChanged)
    def virtualLabs(self) -> list[dict[str, object]]:
        return [info.as_qml_dict() for info in self._virtual_labs]

    @pyqtProperty(int, notify=networkChanged)
    def virtualLabCount(self) -> int:
        return len(self._virtual_labs)

    @pyqtProperty(int, notify=systemInfoChanged)
    def ramUsagePercent(self) -> int:
        return self._ram_usage_percent

__all__ = ["NetworkMonitor"]
