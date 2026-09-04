"""Routing Group orchestration and payload validation."""

from __future__ import annotations

import ipaddress
from typing import Any

from .group_repository import RoutingGroupRepository


class RoutingGroupService:
    """Configure OSPF or EIGRP consistently across multiple selected devices."""

    MAX_HOSTS = 5

    def __init__(self, db: Any) -> None:
        self.db = db
        self.repository = RoutingGroupRepository(db)

    def options(self) -> dict[str, Any]:
        """Return host/network choices already filtered by interface ownership."""
        return {"ok": True, "hosts": self.repository.configuration_hosts()}

    def save(self, protocol: str, targets: list[Any], common: dict[str, Any]) -> dict[str, Any]:
        """Validate group-level input before opening one transaction per host."""
        kind = str(protocol or "").strip().lower()
        if kind not in {"ospf", "eigrp"}:
            return self._error("Protocol must be OSPF or EIGRP")
        normalized = [self.db._as_dict(value) for value in targets]
        normalized = [target for target in normalized if str(target.get("host") or "").strip()]
        if len(normalized) < 2:
            return self._error("Routing Group requires at least two hosts")
        if len(normalized) > self.MAX_HOSTS:
            return self._error(
                f"Routing Group supports at most {self.MAX_HOSTS} hosts"
            )
        hosts = [str(target.get("host") or "").strip() for target in normalized]
        if len(hosts) != len(set(hosts)):
            return self._error("A host can only appear once in a Routing Group")

        router_ids: set[str] = set()
        for target in normalized:
            router_id = str(target.get("router_id") or "").strip()
            if router_id:
                try:
                    ipaddress.IPv4Address(router_id)
                except ValueError:
                    return self._error(f"Invalid Router ID: {router_id}")
                if router_id in router_ids:
                    return self._error(f"Router ID {router_id} is duplicated")
                router_ids.add(router_id)
        return self.repository.save(kind, normalized, common)

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "partial": False,
            "successful": [],
            "failed": [],
            "message": message,
        }
