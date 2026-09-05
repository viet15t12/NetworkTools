"""Minimal, transactional OSPF/EIGRP process cloning."""

from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from copy import deepcopy
from ipaddress import IPv4Address
from typing import Any

from .eigrp import get_eigrp_routing
from .eigrp.process_store import insert_eigrp_process
from .ospf import get_ospf_routing
from .ospf.process_store import insert_ospf_process


_DB_ONLY_KEYS = {
    "id",
    "ospf_id",
    "eigrp_id",
    "area_db_id",
    "iface_id",
    "sync_status",
}


class CloneFailure(ValueError):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class RoutingCloneRepository:
    def __init__(self, db: Any) -> None:
        self.db = db

    def clone_process(
        self,
        source_host: str,
        target_host: str,
        protocol: str,
        source_id: int,
        new_id: int,
        router_id: str | None = None,
        process_only: bool = False,
    ) -> dict[str, Any]:
        protocol = self._protocol(protocol)
        source_host = str(source_host or "").strip()
        target_host = str(target_host or "").strip()
        try:
            new_id = int(new_id)
            if not 1 <= new_id <= 2_147_483_647:
                raise ValueError
        except (TypeError, ValueError):
            return self._error("INVALID_PROCESS_ID", "Process ID/AS must be a positive integer.")
        normalized_router_id = str(router_id or "").strip()
        if normalized_router_id:
            try:
                IPv4Address(normalized_router_id)
            except ValueError:
                return self._error("INVALID_ROUTER_ID", "Router ID must be a valid IPv4 address.")

        try:
            with closing(self.db._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE;")
                target = conn.execute(
                    "SELECT connection_status FROM t01_devices WHERE host = ?;",
                    (target_host,),
                ).fetchone()
                if (
                    source_host == target_host
                    or target is None
                    or target["connection_status"] != "connected"
                ):
                    raise CloneFailure(
                        "TARGET_NOT_CONNECTED",
                        "Target must be a connected device different from the source.",
                    )
                process = self._source_process(source_host, protocol, source_id)
                key = self._process_key(protocol)
                table = self._process_table(protocol)
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE host = ? AND {key} = ? LIMIT 1;",
                    (target_host, new_id),
                ).fetchone():
                    raise CloneFailure(
                        "PROCESS_EXISTS",
                        f"{protocol.upper()} process {new_id} already exists.",
                    )
                if normalized_router_id and conn.execute(
                    f"""
                    SELECT 1 FROM {table}
                    WHERE host = ? AND router_id = ? AND sync_status != 'pending_delete' LIMIT 1;
                    """,
                    (target_host, normalized_router_id),
                ).fetchone():
                    raise CloneFailure(
                        "ROUTER_ID_CONFLICT",
                        f"Router ID {normalized_router_id} already exists on {target_host}.",
                    )

                clone = self._strip_database_state(deepcopy(process))
                clone[key] = new_id
                # Never propagate the source router-id implicitly.
                clone["router_id"] = normalized_router_id or None
                missing = self._missing_interfaces(conn, target_host, clone)
                if missing and not process_only:
                    raise CloneFailure(
                        "MISSING_INTERFACE",
                        "Target is missing interface(s): " + ", ".join(missing),
                    )
                if process_only:
                    clone["interface_settings"] = []

                if protocol == "ospf":
                    insert_ospf_process(conn, self.db, target_host, clone)
                else:
                    insert_eigrp_process(conn, self.db, target_host, clone)
                conn.commit()
            return {
                "ok": True,
                "code": "OK",
                "message": f"Cloned {protocol.upper()} process {new_id} to {target_host}.",
                "missingInterfaces": missing,
            }
        except CloneFailure as exc:
            return self._error(exc.code, exc.reason)
        except (sqlite3.Error, ValueError) as exc:
            return self._error("DATABASE_ERROR", str(exc))

    def validate_target(
        self,
        source_host: str,
        target: dict[str, Any],
        protocol: str,
        source_id: int,
    ) -> dict[str, Any]:
        return self.validate_targets(
            source_host, [target], protocol, source_id
        )[0]

    def validate_targets(
        self,
        source_host: str,
        targets: list[dict[str, Any]],
        protocol: str,
        source_id: int,
    ) -> list[dict[str, Any]]:
        """Validate all targets from one source read and one DB snapshot."""
        protocol = self._protocol(protocol)
        try:
            process = self._source_process(source_host, protocol, source_id)
        except CloneFailure as exc:
            return [
                {
                    "host": str(target.get("host") or "").strip(),
                    "ok": False,
                    "code": exc.code,
                    "reason": exc.reason,
                    "conflictingProcessId": False,
                    "conflictingRouterId": False,
                    "missingInterfaces": [],
                    "matchedInterfaces": [],
                }
                for target in targets
            ]
        hosts = list(
            dict.fromkeys(
                str(target.get("host") or "").strip()
                for target in targets
                if str(target.get("host") or "").strip()
            )
        )
        placeholders = ",".join("?" for _ in hosts) or "NULL"
        table = self._process_table(protocol)
        key = self._process_key(protocol)
        with closing(self.db._connect()) as conn:
            statuses = {
                str(row["host"]): str(row["connection_status"])
                for row in conn.execute(
                    f"SELECT host, connection_status FROM t01_devices WHERE host IN ({placeholders});",
                    tuple(hosts),
                ).fetchall()
            }
            existing = {
                (str(row["host"]), int(row[key]))
                for row in conn.execute(
                    f"SELECT host, {key} FROM {table} WHERE host IN ({placeholders});",
                    tuple(hosts),
                ).fetchall()
            }
            router_ids = {
                (str(row["host"]), str(row["router_id"]))
                for row in conn.execute(
                    f"""
                    SELECT host, router_id FROM {table}
                    WHERE host IN ({placeholders})
                      AND router_id IS NOT NULL AND sync_status != 'pending_delete';
                    """,
                    tuple(hosts),
                ).fetchall()
            }
            interfaces: dict[str, set[str]] = {host: set() for host in hosts}
            for row in conn.execute(
                f"""
                SELECT host, interface_name FROM t02_interface_name
                WHERE host IN ({placeholders}) AND sync_status != 'pending_delete';
                """,
                tuple(hosts),
            ).fetchall():
                interfaces.setdefault(str(row["host"]), set()).add(
                    str(row["interface_name"])
                )

        required = self._interface_names(process)
        results: list[dict[str, Any]] = []
        for target in targets:
            host = str(target.get("host") or "").strip()
            code = ""
            reason = ""
            try:
                new_id = int(target.get("processId"))
            except (TypeError, ValueError):
                new_id = 0
            router_id = str(target.get("routerId") or "").strip()
            router_valid = True
            if router_id:
                try:
                    IPv4Address(router_id)
                except ValueError:
                    router_valid = False
            process_exists = (host, new_id) in existing
            router_conflict = bool(router_id) and (host, router_id) in router_ids
            missing = [
                name for name in required if name not in interfaces.get(host, set())
            ]
            if host == source_host or statuses.get(host) != "connected":
                code, reason = (
                    "TARGET_NOT_CONNECTED",
                    "Target must be connected and different from the source.",
                )
            elif not 1 <= new_id <= 2_147_483_647:
                code, reason = (
                    "INVALID_PROCESS_ID",
                    "Process ID/AS must be a positive integer.",
                )
            elif not router_valid:
                code, reason = (
                    "INVALID_ROUTER_ID",
                    "Router ID must be a valid IPv4 address.",
                )
            elif process_exists:
                code, reason = "PROCESS_EXISTS", "Process ID/AS already exists."
            elif router_conflict:
                code, reason = "ROUTER_ID_CONFLICT", "Router ID already exists."
            elif missing and not bool(target.get("processOnly")):
                code, reason = (
                    "MISSING_INTERFACE",
                    "Target is missing interface(s): " + ", ".join(missing),
                )
            results.append(
                {
                    "host": host,
                    "ok": not code,
                    "code": code or "OK",
                    "reason": reason,
                    "conflictingProcessId": process_exists,
                    "conflictingRouterId": router_conflict,
                    "missingInterfaces": missing,
                    "matchedInterfaces": [
                        name for name in required if name not in missing
                    ],
                }
            )
        return results

    def _source_process(
        self, source_host: str, protocol: str, source_id: int
    ) -> dict[str, Any]:
        protocol = self._protocol(protocol)
        payload = (
            get_ospf_routing(self.db, source_host)
            if protocol == "ospf"
            else get_eigrp_routing(self.db, source_host)
        )
        id_key = "ospf_id" if protocol == "ospf" else "eigrp_id"
        for process in payload.get("processes") or []:
            if int(process.get(id_key) or 0) == int(source_id):
                return process
        raise CloneFailure(
            "SOURCE_PROCESS_NOT_FOUND",
            "The selected source process no longer exists.",
        )

    @staticmethod
    def _interface_names(process: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(row.get("interface_name") or "").strip()
                for row in process.get("interface_settings") or []
                if str(row.get("interface_name") or "").strip()
            }
        )

    def _missing_interfaces(
        self, conn: sqlite3.Connection, host: str, process: dict[str, Any]
    ) -> list[str]:
        required = self._interface_names(process)
        if not required:
            return []
        available = {
            str(row["interface_name"])
            for row in conn.execute(
                "SELECT interface_name FROM t02_interface_name WHERE host = ? AND sync_status != 'pending_delete';",
                (host,),
            ).fetchall()
        }
        return [name for name in required if name not in available]

    @classmethod
    def _strip_database_state(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._strip_database_state(item) for item in value]
        if not isinstance(value, dict):
            return value
        return {
            key: cls._strip_database_state(item)
            for key, item in value.items()
            if key not in _DB_ONLY_KEYS
        }

    @staticmethod
    def _protocol(protocol: str) -> str:
        value = str(protocol or "").strip().lower()
        if value not in {"ospf", "eigrp"}:
            raise CloneFailure("DATABASE_ERROR", "Protocol must be ospf or eigrp.")
        return value

    @staticmethod
    def _process_key(protocol: str) -> str:
        return "process_id" if str(protocol).lower() == "ospf" else "as_number"

    @staticmethod
    def _process_table(protocol: str) -> str:
        return (
            "t04_ospf_processes"
            if str(protocol).lower() == "ospf"
            else "t04_eigrp_processes"
        )

    @staticmethod
    def _error(code: str, reason: str) -> dict[str, Any]:
        return {"ok": False, "code": code, "message": reason, "reason": reason}
