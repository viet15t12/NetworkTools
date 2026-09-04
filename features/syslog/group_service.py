"""Validation and orchestration for multi-device Syslog groups."""

from __future__ import annotations

from typing import Any

from .group_repository import SyslogGroupRepository
from .persistence.device_state_repository import DeviceStateRepository
from .repository import SyslogRepository


class SyslogGroupService:
    """Stage a common Syslog destination for two to five Cisco devices."""

    MAX_HOSTS = 5

    def __init__(self, repository: SyslogRepository) -> None:
        self.repository = repository
        self.group_repository = SyslogGroupRepository(repository)

    def options(self) -> dict[str, Any]:
        return {"ok": True, "hosts": self.group_repository.configuration_hosts()}

    def save(
        self, targets: list[Any], common: dict[str, Any]
    ) -> dict[str, Any]:
        normalized = [dict(value) for value in targets if isinstance(value, dict)]
        normalized = [
            target for target in normalized
            if str(target.get("host") or "").strip()
        ]
        if len(normalized) < 2:
            return self._error("Syslog Group requires at least two hosts")
        if len(normalized) > self.MAX_HOSTS:
            return self._error(
                f"Syslog Group supports at most {self.MAX_HOSTS} hosts"
            )
        hosts = [str(target.get("host") or "").strip() for target in normalized]
        if len(hosts) != len(set(hosts)):
            return self._error("A host can only appear once in a Syslog Group")

        # Validate the shared policy once before staging any host. Per-host
        # ownership and connectivity are checked independently by the repository.
        probe = dict(common)
        probe["source_interface"] = "Loopback0"
        try:
            DeviceStateRepository._clean_configuration(hosts[0], probe)
        except ValueError as exc:
            return self._error(str(exc))
        return self.group_repository.save(normalized, common)

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "partial": False,
            "successful": [],
            "failed": [],
            "message": message,
        }


__all__ = ["SyslogGroupService"]
