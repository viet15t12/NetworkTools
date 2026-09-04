"""Persistence and inventory queries for multi-device Syslog groups."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from .persistence.connections import device_connection
from .repository import SyslogRepository


SUPPORTED_GROUP_OS = {
    "cisco",
    "ios",
    "ios_xe",
    "cisco_ios",
    "cisco_ios_telnet",
    "cisco_xe",
}


class SyslogGroupRepository:
    """Stage one shared Syslog policy independently for every selected host."""

    def __init__(self, repository: SyslogRepository) -> None:
        self.repository = repository

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone() is not None

    def configuration_hosts(self) -> list[dict[str, Any]]:
        """Return connected Cisco hosts and source interfaces owned by each host."""
        with closing(device_connection(self.repository.device_db)) as conn:
            hosts = conn.execute(
                """
                SELECT host, device_name, role, device_type, os
                FROM t01_devices
                WHERE connection_status = 'connected'
                ORDER BY COALESCE(NULLIF(TRIM(device_name), ''), host)
                         COLLATE NOCASE;
                """
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in hosts:
                if str(row["os"] or "").strip().lower() not in SUPPORTED_GROUP_OS:
                    continue
                interfaces = self._source_interfaces(conn, str(row["host"]))
                result.append(
                    {
                        "host": str(row["host"]),
                        "device_name": str(row["device_name"] or ""),
                        "role": str(row["role"] or row["device_type"] or ""),
                        "interfaces": interfaces,
                        "recommended_interface": self._recommended_interface(
                            interfaces, str(row["host"])
                        ),
                    }
                )
        return result

    def _source_interfaces(
        self, conn: sqlite3.Connection, host: str
    ) -> list[dict[str, str]]:
        candidates: dict[str, dict[str, str]] = {}

        def add(name: Any, kind: str, address: Any = "") -> None:
            text = str(name or "").strip()
            if not text:
                return
            key = text.casefold()
            candidates.setdefault(
                key,
                {"name": text, "kind": kind, "ip_address": str(address or "")},
            )

        if self._table_exists(conn, "t02_interface_name"):
            rows = conn.execute(
                """
                SELECT interface_name, ip_address
                FROM t02_interface_name
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY interface_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
            for row in rows:
                add(row["interface_name"], "router", row["ip_address"])

        if self._table_exists(conn, "t06_interface_l2"):
            rows = conn.execute(
                """
                SELECT if_name FROM t06_interface_l2
                WHERE host = ? AND success != 'pending_delete'
                ORDER BY if_name COLLATE NOCASE;
                """,
                (host,),
            ).fetchall()
            for row in rows:
                add(row["if_name"], "switch")

        if self._table_exists(conn, "t06_svi_interface"):
            rows = conn.execute(
                """
                SELECT vlan_id, ip_address FROM t06_svi_interface
                WHERE host = ? AND sync_status != 'pending_delete'
                ORDER BY vlan_id;
                """,
                (host,),
            ).fetchall()
            for row in rows:
                add(f"Vlan{int(row['vlan_id'])}", "svi", row["ip_address"])

        if self._table_exists(conn, "t06_etherchannel"):
            rows = conn.execute(
                """
                SELECT po_number FROM t06_etherchannel
                WHERE host = ? AND success != 'pending_delete'
                ORDER BY po_number;
                """,
                (host,),
            ).fetchall()
            for row in rows:
                add(f"Port-channel{int(row['po_number'])}", "etherchannel")

        return sorted(candidates.values(), key=lambda item: item["name"].casefold())

    @staticmethod
    def _recommended_interface(
        interfaces: list[dict[str, str]], host: str
    ) -> str:
        if not interfaces:
            return ""
        for item in interfaces:
            if item["name"].casefold().startswith("loopback"):
                return item["name"]
        for item in interfaces:
            if item.get("ip_address") == host:
                return item["name"]
        for item in interfaces:
            if item["kind"] == "svi":
                return item["name"]
        return interfaces[0]["name"]

    def save(
        self, targets: list[dict[str, Any]], common: dict[str, Any]
    ) -> dict[str, Any]:
        successful: list[str] = []
        failed: list[dict[str, str]] = []
        for target in targets:
            host = str(target.get("host") or "").strip()
            try:
                source_interface = self._validate_target(host, target)
                payload = dict(common)
                payload["source_interface"] = source_interface
                result = self.repository.save_configuration(host, payload)
                if not bool(result.get("ok")):
                    raise ValueError(
                        str(result.get("message") or "Could not save Syslog policy")
                    )
                successful.append(host)
            except (sqlite3.Error, ValueError) as exc:
                failed.append({"host": host, "reason": str(exc)})

        message = (
            f"Syslog Group saved: {len(successful)} succeeded, "
            f"{len(failed)} failed."
        )
        if failed:
            message += " Failed hosts: " + "; ".join(
                f"{item['host']}: {item['reason']}" for item in failed
            ) + "."
        return {
            "ok": bool(successful) and not failed,
            "partial": bool(successful) and bool(failed),
            "successful": successful,
            "failed": failed,
            "message": message,
        }

    def _validate_target(self, host: str, target: dict[str, Any]) -> str:
        if not host:
            raise ValueError("Host is required")
        requested = str(target.get("source_interface") or "").strip()
        if not requested:
            raise ValueError("Source interface is required")
        with closing(device_connection(self.repository.device_db)) as conn:
            device = conn.execute(
                """
                SELECT os FROM t01_devices
                WHERE host = ? AND connection_status = 'connected'
                LIMIT 1;
                """,
                (host,),
            ).fetchone()
            if device is None:
                raise ValueError("Host is not connected")
            if str(device["os"] or "").strip().lower() not in SUPPORTED_GROUP_OS:
                raise ValueError("Syslog Group currently supports Cisco IOS/IOS-XE only")
            allowed = {
                item["name"].casefold(): item["name"]
                for item in self._source_interfaces(conn, host)
            }
        canonical = allowed.get(requested.casefold())
        if canonical is None:
            raise ValueError(f"Source interface {requested} is not available on {host}")
        return canonical


__all__ = ["SUPPORTED_GROUP_OS", "SyslogGroupRepository"]
