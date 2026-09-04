"""QML slots grouped by the routing responsibility."""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from typing import Any

from PyQt6.QtCore import pyqtSlot
from infrastructure.database.paths import require_database

from features.routing import (
    get_eigrp_routing,
    get_ospf_routing,
    get_static_routing,
    save_eigrp_routing,
    save_ospf_routing,
    save_static_routing,
    save_static_routes,
    get_default_routes,
    save_default_routes,
)
from features.routing.clone_service import RoutingCloneService
from features.routing.group_service import RoutingGroupService
from .conversion import _variant_list


class RoutingSlotsMixin:
    """Provide the stable QML contract for this responsibility."""

    @pyqtSlot(result="QVariant")
    def getRoutingGroupOptions(self) -> dict[str, Any]:
        """Return connected hosts and interface-derived networks for Routing Group."""
        return RoutingGroupService(self).options()

    @pyqtSlot(str, "QVariant", "QVariant", result="QVariant")
    def saveRoutingGroup(
        self, protocol: str, targets: Any, common_parameters: Any
    ) -> dict[str, Any]:
        """Persist a multi-host OSPF/EIGRP group with independent host identities."""
        normalized_targets = [self._as_dict(value) for value in self._as_list(targets)]
        return RoutingGroupService(self).save(
            protocol,
            normalized_targets,
            self._as_dict(common_parameters),
        )

    # Compatibility API for older automation. The QML clone workflow has been
    # replaced by Routing Group and no longer calls the slots below.
    @pyqtSlot(str, result="QVariant")
    @pyqtSlot(str, str, result="QVariant")
    def getRoutingCloneOptions(
        self, source_host: str, protocol: str = ""
    ) -> dict[str, Any]:
        """Return connected target hosts available to the clone dialog."""
        if not protocol:
            protocol = source_host
            source_host = ""
        return {
            "hosts": RoutingCloneService(self).connected_hosts(source_host),
            "protocol": str(protocol or "").strip().lower(),
        }

    @pyqtSlot(str, str, result="QVariant")
    def getRoutingCloneProcesses(self, host: str, protocol: str) -> list[dict[str, Any]]:
        """Return cloneable processes for one source host and protocol."""
        return RoutingCloneService(self).processes(host, protocol)

    @pyqtSlot(str, str, int, result=bool)
    def routingCloneProcessExists(self, host: str, protocol: str, process_id: int) -> bool:
        """Check whether a protocol process identifier exists on one target."""
        return RoutingCloneService(self).process_exists(host, protocol, process_id)

    @pyqtSlot(str, str, str, int, int, result="QVariant")
    def cloneRoutingProcess(
        self, source_host: str, target_host: str, protocol: str, source_index: int, new_id: int
    ) -> dict[str, Any]:
        """Clone one routing process to one target for legacy consumers."""
        return RoutingCloneService(self).clone(source_host, target_host, protocol, source_index, new_id)

    @pyqtSlot(str, "QVariant", str, int, int, result="QVariant")
    def cloneRoutingProcesses(
        self, source_host: str, target_hosts: Any, protocol: str, source_index: int, new_id: int
    ) -> dict[str, Any]:
        """Clone one routing process to multiple targets sharing one identifier."""
        # QML JavaScript arrays arrive as QJSValue at runtime. ConversionMixin
        # unwraps them with toVariant() before enforcing the list contract.
        hosts = [str(host) for host in self._as_list(target_hosts)]
        return RoutingCloneService(self).clone_many(source_host, hosts, protocol, source_index, new_id)

    @pyqtSlot(str, "QVariant", str, int, result="QVariant")
    def cloneRoutingTargets(
        self, source_host: str, targets: Any, protocol: str, source_id: int
    ) -> dict[str, Any]:
        """Clone using independent process and router identifiers per target."""
        normalized = [self._as_dict(target) for target in self._as_list(targets)]
        return RoutingCloneService(self).clone_targets(
            source_host, normalized, protocol, source_id
        )

    @pyqtSlot(str, str, int, "QVariant", result="QVariant")
    def validateRoutingCloneTargets(
        self, source_host: str, protocol: str, source_id: int, targets: Any
    ) -> list[dict[str, Any]]:
        """Batch-check clone identifiers and interface compatibility for QML."""
        normalized = [self._as_dict(target) for target in self._as_list(targets)]
        return RoutingCloneService(self).validate_targets(
            source_host, protocol, source_id, normalized
        )

    def _set_last_routing_error(self, message: str) -> None:
        """Store the latest routing error exposed through the compatibility slot."""
        self._last_routing_error = (message or "").strip()

    @pyqtSlot(result=str)
    def getLastRoutingError(self) -> str:
        """Return the latest routing operation error message."""
        return self._last_routing_error

    @pyqtSlot(str, result="QVariant")
    def getRoutingInfo(self, host: str) -> dict[str, Any]:
        """Đọc bảng routing đã thu thập từ DB cho một thiết bị."""
        host = (host or "").strip()
        if not host:
            return {"ok": False, "message": "Host is empty", "routes": []}
        try:
            # Collected routing snapshots live in info_collected.db, separate
            # from editable device configuration in device_network.db.
            with closing(sqlite3.connect(require_database(self.info_db_path), timeout=10.0)) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA busy_timeout = 10000;")
                rows = conn.execute(
                    """
                    SELECT id, host, protocol_code, protocol_name,
                           destination, prefix_length, administrative_distance,
                           metric, next_hop, route_age, exit_interface,
                           is_best, collected_at, raw_line
                    FROM t08_info_routing_table
                    WHERE host = ?
                    ORDER BY
                        is_best DESC,
                        protocol_code COLLATE NOCASE,
                        destination COLLATE NOCASE,
                        prefix_length DESC,
                        id ASC;
                    """,
                    (host,),
                ).fetchall()
            routes: list[dict[str, Any]] = []
            for row in rows:
                routes.append(
                    {
                        "id": row["id"],
                        "host": row["host"] or "",
                        "protocol_code": row["protocol_code"] or "",
                        "protocol_name": row["protocol_name"] or "",
                        "destination": row["destination"] or "",
                        "prefix_length": row["prefix_length"] if row["prefix_length"] is not None else "",
                        "administrative_distance": row["administrative_distance"] if row["administrative_distance"] is not None else "",
                        "metric": row["metric"] if row["metric"] is not None else "",
                        "next_hop": row["next_hop"] or "",
                        "route_age": row["route_age"] or "",
                        "exit_interface": row["exit_interface"] or "",
                        "is_best": row["is_best"] if row["is_best"] is not None else 0,
                        "collected_at": row["collected_at"] or "",
                        "raw_line": row["raw_line"] or "",
                    }
                )
            return {"ok": True, "message": "Loaded routing table info", "routes": _variant_list(routes)}
        except sqlite3.Error as exc:
            print(f"[db] getRoutingInfo failed: {exc}", file=sys.stderr)
            return {"ok": False, "message": str(exc), "routes": []}

    @pyqtSlot(str, result="QVariant")
    def getStaticRouting(self, host: str) -> dict[str, Any]:
        """Load static-routing data for a host through the routing feature."""
        return get_static_routing(self, host)

    @pyqtSlot(str, str, "QVariant", result=bool)
    def saveStaticRouting(self, host: str, default_value: str, routes: Any) -> bool:
        """Validate and persist static-routing changes through the routing feature."""
        self._set_last_routing_error("")
        ok = save_static_routing(self, host, default_value, routes)
        return ok

    @pyqtSlot(str, "QVariant", result=bool)
    def saveStaticRoutes(self, host: str, routes: Any) -> bool:
        """Persist static routes without modifying default routes."""
        self._set_last_routing_error("")
        return save_static_routes(self, host, routes)

    @pyqtSlot(str, result="QVariant")
    def getDefaultRoutes(self, host: str) -> dict[str, Any]:
        """Load default routes for a host through the routing feature."""
        return get_default_routes(self, host)

    @pyqtSlot(str, "QVariant", result=bool)
    def saveDefaultRoutes(self, host: str, routes: Any) -> bool:
        """Validate and persist default-route changes through the routing feature."""
        self._set_last_routing_error("")
        return save_default_routes(self, host, routes)

    @pyqtSlot(str, result="QVariant")
    def getOspfRouting(self, host: str) -> dict[str, Any]:
        """Load OSPF routing data for a host through the routing feature."""
        return get_ospf_routing(self, host)

    @pyqtSlot(str, "QVariant", result=bool)
    def saveOspfRouting(self, host: str, payload: Any) -> bool:
        """Validate and persist OSPF changes through the routing feature."""
        self._set_last_routing_error("")
        ok = save_ospf_routing(self, host, payload)
        return ok

    @pyqtSlot(str, result="QVariant")
    def getEigrpRouting(self, host: str) -> dict[str, Any]:
        """Load EIGRP routing data for a host through the routing feature."""
        return get_eigrp_routing(self, host)

    @pyqtSlot(str, "QVariant", result=bool)
    def saveEigrpRouting(self, host: str, payload: Any) -> bool:
        """Validate and persist EIGRP changes through the routing feature."""
        self._set_last_routing_error("")
        ok = save_eigrp_routing(self, host, payload)
        return ok
