"""Framework-independent orchestration for the Syslog server and device actions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..device_config.service import SyslogConfigurator
from ..domain.models import ListenerConfig
from ..repository import SyslogRepository
from .pipeline import SyslogPipeline
from .retention import run_retention
from .writer import SyslogWriter


class SyslogServerService:
    def __init__(
        self,
        info_db: Path,
        device_db: Path,
        on_inserted: Callable[[list[dict[str, Any]]], None],
        on_writer_error: Callable[[str], None],
        on_receiver_error: Callable[[str], None],
    ) -> None:
        self.repository = SyslogRepository(info_db, device_db)
        self.configurator = SyslogConfigurator(self.repository)
        self.writer = SyslogWriter(self.repository, on_inserted, on_writer_error)
        self.pipeline = SyslogPipeline(self.writer, on_receiver_error)

    @property
    def receiver(self) -> object | None:
        return self.pipeline.receiver

    @property
    def dropped(self) -> int:
        return self.writer.dropped

    def set_database_paths(self, info_db: Path, device_db: Path) -> None:
        self.pipeline.stop()
        repository = SyslogRepository(info_db, device_db)
        self.repository = repository
        self.configurator.repository = repository
        self.writer.set_repository(repository)

    def start(self, config: ListenerConfig, retention_days: int) -> dict[str, object]:
        self.pipeline.start(config)
        return run_retention(self.repository, retention_days)

    def stop(self, *, receiver_timeout: float = 3.0, writer_timeout: float = 5.0) -> None:
        self.pipeline.stop(receiver_timeout=receiver_timeout, writer_timeout=writer_timeout)

    def query_messages(
        self, filters: dict[str, Any], before_id: int = 0, limit: int = 200,
    ) -> list[dict[str, Any]]:
        return self.repository.query_messages(filters, before_id, limit)

    def connected_devices(self, config: ListenerConfig | None = None) -> list[dict[str, Any]]:
        devices = self.repository.connected_devices()
        configured_hosts = set()
        if config is not None:
            configured_hosts = self.repository.configured_hosts(
                config.advertised_ip, config.protocol, config.port
            )
        for row in devices:
            row["configured"] = row["host"] in configured_hosts
        return devices

    def configure_device(
        self, host: str, config: ListenerConfig, source_interface: str = "",
    ) -> dict[str, object]:
        # Compatibility action predates per-device destinations. A dual local
        # listener does not imply two Cisco destinations, so retain UDP here.
        protocol = "udp" if config.protocol == "both" else config.protocol
        return self.configurator.configure(
            host, config.advertised_ip, protocol, config.port, source_interface
        )

    def cancel_device(self, host: str, config: ListenerConfig) -> dict[str, object]:
        protocol = "udp" if config.protocol == "both" else config.protocol
        return self.configurator.cancel(
            host, config.advertised_ip, protocol, config.port
        )


__all__ = ["SyslogServerService"]
