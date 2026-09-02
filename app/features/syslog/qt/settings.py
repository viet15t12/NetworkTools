"""Persistent JSON settings adapter shared by QML and the C++ collector."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
from ipaddress import ip_address

from PyQt6.QtCore import QObject, QSettings, QStandardPaths, pyqtProperty, pyqtSignal, pyqtSlot

from ..domain.models import ListenerConfig


def _local_ipv4_addresses() -> list[str]:
    try:
        import psutil  # type: ignore
        addresses_by_name = psutil.net_if_addrs()
        stats_by_name = psutil.net_if_stats()
    except Exception:
        return []
    addresses: list[str] = []
    for interface_name, interface_addresses in addresses_by_name.items():
        stats = stats_by_name.get(interface_name)
        if stats is not None and not stats.isup:
            continue
        for item in interface_addresses:
            if item.family != socket.AF_INET:
                continue
            value = str(item.address or "").strip()
            try:
                address = ip_address(value)
            except ValueError:
                continue
            if address.is_loopback or address.is_unspecified or address.is_link_local:
                continue
            if value not in addresses:
                addresses.append(value)
    return addresses


def _validate_ip(value: str, field_name: str, *, allow_unspecified: bool) -> None:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid IPv4 or IPv6 address") from exc
    if not allow_unspecified and address.is_unspecified:
        raise ValueError(f"{field_name} cannot be 0.0.0.0 or ::")


class SyslogSettings(QObject):
    changed = pyqtSignal()

    DEFAULTS = {
        "enabled_on_startup": False,
        "protocol": "both",
        "bind_ip": "0.0.0.0",
        "advertised_ip": "",
        "port": 5514,
        "retention_days": 30,
        "max_message_bytes": 16384,
        "max_tcp_clients": 64,
    }

    def __init__(
        self, parent: QObject | None = None, *, settings_path: str | Path | None = None
    ) -> None:
        super().__init__(parent)
        self._available_advertised_ips = _local_ipv4_addresses()
        override = os.environ.get("CAMS_SYSLOG_SETTINGS", "").strip()
        default_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        self._path = Path(settings_path or override or (default_root / "syslog.json")).expanduser()
        self._values = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> dict[str, object]:
        values = dict(self.DEFAULTS)
        if self._path.is_file():
            try:
                stored = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    values.update({key: stored[key] for key in values if key in stored})
                    return values
            except (OSError, json.JSONDecodeError):
                pass
        # One-time migration from the former QSettings keys.
        legacy = QSettings()
        for key, default in self.DEFAULTS.items():
            old = legacy.value(f"syslog/{key}", None)
            if old is not None:
                if isinstance(default, bool):
                    values[key] = str(old).lower() in {"1", "true"}
                elif isinstance(default, int):
                    values[key] = int(old)
                else:
                    values[key] = str(old)
        self._write(values)
        return values

    def _write(self, values: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(self._path)

    def _get(self, key: str, default: object) -> object:
        return self._values.get(key, default)

    def _set(self, key: str, value: object) -> None:
        self._values[key] = value
        self._write(self._values)
        self.changed.emit()

    @pyqtProperty(bool, notify=changed)
    def enabledOnStartup(self) -> bool:
        return str(self._get("enabled_on_startup", "false")).lower() in {"1", "true"}

    @enabledOnStartup.setter
    def enabledOnStartup(self, value: bool) -> None:
        self._set("enabled_on_startup", bool(value))

    @pyqtProperty(str, notify=changed)
    def protocol(self) -> str:
        # The local collector always owns both transports. Individual device
        # destinations still choose UDP or TCP independently.
        return "both"

    @protocol.setter
    def protocol(self, value: str) -> None:
        self._set("protocol", "both")

    @pyqtProperty(str, notify=changed)
    def bindIp(self) -> str:
        return str(self._get("bind_ip", "0.0.0.0"))

    @bindIp.setter
    def bindIp(self, value: str) -> None:
        self._set("bind_ip", value.strip())

    @pyqtProperty(str, notify=changed)
    def advertisedIp(self) -> str:
        stored = str(self._get("advertised_ip", "")).strip()
        if stored:
            return stored
        return self._available_advertised_ips[0] if self._available_advertised_ips else ""

    @advertisedIp.setter
    def advertisedIp(self, value: str) -> None:
        self._set("advertised_ip", value.strip())

    @pyqtProperty("QVariantList", notify=changed)
    def availableAdvertisedIps(self) -> list[str]:
        return list(self._available_advertised_ips)

    @pyqtSlot()
    def refreshLocalIps(self) -> None:
        addresses = _local_ipv4_addresses()
        if addresses == self._available_advertised_ips:
            return
        self._available_advertised_ips = addresses
        self.changed.emit()

    @pyqtProperty(int, notify=changed)
    def port(self) -> int:
        return int(self._get("port", 5514))

    @port.setter
    def port(self, value: int) -> None:
        self._set("port", int(value))

    @pyqtProperty(int, notify=changed)
    def retentionDays(self) -> int:
        return int(self._get("retention_days", 30))

    @retentionDays.setter
    def retentionDays(self, value: int) -> None:
        self._set("retention_days", max(1, int(value)))

    @pyqtProperty(int, notify=changed)
    def maxMessageBytes(self) -> int:
        return int(self._get("max_message_bytes", 16 * 1024))

    @maxMessageBytes.setter
    def maxMessageBytes(self, value: int) -> None:
        self._set("max_message_bytes", min(1024 * 1024, max(1024, int(value))))

    @pyqtProperty(int, notify=changed)
    def maxTcpClients(self) -> int:
        return int(self._get("max_tcp_clients", 64))

    @maxTcpClients.setter
    def maxTcpClients(self, value: int) -> None:
        self._set("max_tcp_clients", min(4096, max(1, int(value))))

    @pyqtSlot(result="QVariant")
    def validateListener(self) -> dict[str, object]:
        try:
            _validate_ip(self.bindIp, "Bind IP", allow_unspecified=True)
            if not 1 <= self.port <= 65535:
                raise ValueError("Port must be between 1 and 65535")
            if self.protocol != "both":
                raise ValueError("The Syslog listener must enable UDP and TCP")
            if not 1024 <= self.maxMessageBytes <= 1024 * 1024:
                raise ValueError("Maximum message size must be between 1024 and 1048576 bytes")
            if not 1 <= self.maxTcpClients <= 4096:
                raise ValueError("Maximum TCP clients must be between 1 and 4096")
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": "Syslog listener settings are valid."}

    @pyqtSlot(result="QVariant")
    def validate(self) -> dict[str, object]:
        listener_result = self.validateListener()
        if not listener_result["ok"]:
            return listener_result
        try:
            _validate_ip(self.advertisedIp, "Advertised/server IP", allow_unspecified=False)
            if self.advertisedIp not in self._available_advertised_ips:
                raise ValueError(
                    "Advertised/server IP must be assigned to an active network interface on this machine"
                )
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": "Syslog settings are valid."}

    def listener_config(self) -> ListenerConfig:
        result = self.validateListener()
        if not result["ok"]:
            raise ValueError(str(result["message"]))
        return ListenerConfig(
            self.bindIp,
            self.advertisedIp,
            self.port,
            self.protocol,
            self.maxMessageBytes,
            self.maxTcpClients,
        )


__all__ = ["SyslogSettings", "_local_ipv4_addresses", "_validate_ip"]
