"""Transactional persistence and inventory queries for multi-device routing groups."""

from __future__ import annotations

import ipaddress
import sqlite3
from contextlib import closing
from typing import Any

from .eigrp.child_sync import CHILD_TABLES, sync_eigrp_child_table
from .eigrp.process_store import insert_eigrp_process, update_eigrp_process_row
from .ospf.process_store import insert_ospf_process


def _interface_network(ip_value: Any, mask_value: Any) -> ipaddress.IPv4Network | None:
    """Return the usable IPv4 network for one configured router interface."""
    ip_text = str(ip_value or "").strip()
    mask_text = str(mask_value or "").strip()
    if not ip_text or not mask_text:
        return None
    try:
        return ipaddress.ip_interface(f"{ip_text}/{mask_text}").network
    except ValueError:
        return None


class RoutingGroupRepository:
    """Keep routing-group database work independent from QML and device workers."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def configuration_hosts(self) -> list[dict[str, Any]]:
        """Return connected router/L3-switch hosts with their candidate networks."""
        with closing(self.db._connect()) as conn:
            hosts = conn.execute(
                """
                SELECT host, device_name, role, device_type
                FROM t01_devices
                WHERE connection_status = 'connected'
                  AND (
                    lower(COALESCE(role, '')) IN ('rou', 'router', 'sw3')
                    OR lower(COALESCE(device_type, '')) IN ('router', 'sw3')
                  )
                ORDER BY host COLLATE NOCASE;
                """
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in hosts:
                interfaces = conn.execute(
                    """
                    SELECT iface_id, interface_name, ip_address, subnet_mask
                    FROM t02_interface_name
                    WHERE host = ?
                      AND sync_status != 'pending_delete'
                      AND COALESCE(ip_address, '') != ''
                      AND COALESCE(subnet_mask, '') != ''
                    ORDER BY interface_name COLLATE NOCASE;
                    """,
                    (row["host"],),
                ).fetchall()
                networks: dict[tuple[str, str], dict[str, Any]] = {}
                for interface in interfaces:
                    network = _interface_network(interface["ip_address"], interface["subnet_mask"])
                    if network is None:
                        continue
                    key = (str(network.network_address), str(network.hostmask))
                    entry = networks.setdefault(
                        key,
                        {
                            "network": key[0],
                            "wildcard": key[1],
                            "prefix_length": network.prefixlen,
                            "interfaces": [],
                        },
                    )
                    entry["interfaces"].append(
                        {
                            "iface_id": interface["iface_id"],
                            "interface_name": interface["interface_name"],
                            "ip_address": interface["ip_address"],
                            "subnet_mask": interface["subnet_mask"],
                        }
                    )
                result.append(
                    {
                        "host": row["host"],
                        "device_name": row["device_name"] or "",
                        "networks": list(networks.values()),
                    }
                )
        return result

    def save(self, protocol: str, targets: list[dict[str, Any]], common: dict[str, Any]) -> dict[str, Any]:
        """Persist one independently identified process for every selected host."""
        successful: list[str] = []
        failed: list[dict[str, str]] = []
        for target in targets:
            host = str(target.get("host") or "").strip()
            try:
                # DatabaseManager connections intentionally close when their
                # transaction context exits.  Give every host an independent
                # connection so one rollback cannot invalidate later hosts.
                with closing(self.db._connect()) as conn:
                    with conn:
                        self._validate_target(conn, protocol, target)
                        process = self._process_payload(protocol, target, common)
                        if protocol == "ospf":
                            insert_ospf_process(conn, self.db, host, process)
                        else:
                            self._save_eigrp_process(conn, host, process)
                successful.append(host)
            except (sqlite3.Error, ValueError) as exc:
                failed.append({"host": host, "reason": str(exc)})
        message = (
            f"Routing Group saved: {len(successful)} succeeded, {len(failed)} failed."
        )
        if failed:
            details = "; ".join(
                f"{item['host']}: {item['reason']}" for item in failed
            )
            message += f" Failed hosts: {details}."
        return {
            "ok": bool(successful) and not failed,
            "partial": bool(successful) and bool(failed),
            "successful": successful,
            "failed": failed,
            "message": message,
        }

    def _validate_target(
        self, conn: sqlite3.Connection, protocol: str, target: dict[str, Any]
    ) -> None:
        host = str(target.get("host") or "").strip()
        identifier_key = "process_id" if protocol == "ospf" else "as_number"
        identifier = self.db._int_or_none(target.get(identifier_key))
        if not host:
            raise ValueError("Host is required")
        if identifier is None or identifier < 1:
            raise ValueError(f"{identifier_key} must be a positive integer")
        inventory = conn.execute(
            """
            SELECT 1 FROM t01_devices
            WHERE host = ? AND connection_status = 'connected'
            LIMIT 1;
            """,
            (host,),
        ).fetchone()
        if inventory is None:
            raise ValueError("Host is not connected")

        table = "t04_ospf_processes" if protocol == "ospf" else "t04_eigrp_processes"
        column = "process_id" if protocol == "ospf" else "as_number"
        duplicate = conn.execute(
            f"""
            SELECT sync_status FROM {table}
            WHERE host = ? AND {column} = ? AND sync_status != 'pending_delete'
            LIMIT 1;
            """,
            (host, identifier),
        ).fetchone()
        # A previous partial group save may already have staged this process
        # locally. Both persistence implementations can replace that pending
        # payload, so retrying OSPF or EIGRP remains idempotent. Never overwrite
        # synchronized (or skipped) device state implicitly.
        retryable_draft = (
            duplicate is not None and duplicate["sync_status"] == "pending_apply"
        )
        if duplicate is not None and not retryable_draft:
            raise ValueError(f"{column} {identifier} already exists on {host}")

        allowed = {
            (row["network"], row["wildcard"])
            for row in self._candidate_network_rows(conn, host)
        }
        submitted: set[tuple[str, str]] = set()
        for network in target.get("networks") or []:
            key = (
                str(network.get("network") or "").strip(),
                str(network.get("wildcard") or "").strip(),
            )
            if key not in allowed:
                raise ValueError(f"Network {key[0]} is not connected to {host}")
            if key in submitted:
                raise ValueError(f"Network {key[0]} is duplicated")
            submitted.add(key)
        if not submitted:
            raise ValueError("Select at least one connected network")

    def _save_eigrp_process(
        self, conn: sqlite3.Connection, host: str, process: dict[str, Any]
    ) -> int:
        """Insert a new EIGRP draft or replace the same pending group draft."""
        as_number = self.db._int_or_none(process.get("as_number"))
        existing = conn.execute(
            """
            SELECT eigrp_id
            FROM t04_eigrp_processes
            WHERE host = ? AND as_number = ? AND sync_status = 'pending_apply'
            LIMIT 1;
            """,
            (host, as_number),
        ).fetchone()
        if existing is None:
            return insert_eigrp_process(conn, self.db, host, process)

        eigrp_id = int(existing["eigrp_id"])
        update_eigrp_process_row(conn, self.db, eigrp_id, process)
        for table in CHILD_TABLES:
            sync_eigrp_child_table(
                conn,
                self.db,
                eigrp_id,
                process,
                table,
                replace_all=False,
            )
        return eigrp_id

    def _candidate_network_rows(
        self, conn: sqlite3.Connection, host: str
    ) -> list[dict[str, str]]:
        rows = conn.execute(
            """
            SELECT ip_address, subnet_mask
            FROM t02_interface_name
            WHERE host = ?
              AND sync_status != 'pending_delete'
              AND COALESCE(ip_address, '') != ''
              AND COALESCE(subnet_mask, '') != '';
            """,
            (host,),
        ).fetchall()
        candidates: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            network = _interface_network(row["ip_address"], row["subnet_mask"])
            if network is None:
                continue
            key = (str(network.network_address), str(network.hostmask))
            candidates[key] = {"network": key[0], "wildcard": key[1]}
        return list(candidates.values())

    def _process_payload(
        self, protocol: str, target: dict[str, Any], common: dict[str, Any]
    ) -> dict[str, Any]:
        networks = []
        for row in target.get("networks") or []:
            network = {
                "network": str(row.get("network") or "").strip(),
                "wildcard": str(row.get("wildcard") or "").strip(),
            }
            if protocol == "ospf":
                network["area"] = self.db._int_or_zero(row.get("area"))
            else:
                network["interface_name"] = ""
            networks.append(network)

        if protocol == "ospf":
            areas: dict[int, dict[str, Any]] = {}
            authentication_cfg = bool(common.get("authentication_cfg"))
            for row in networks:
                area = int(row["area"])
                areas[area] = {
                    "area_id": area,
                    "area_type": "normal",
                    "no_summary": False,
                    "authentication": "message-digest" if authentication_cfg else "",
                    "ranges": [],
                }
            return {
                "process_id": target.get("process_id"),
                "router_id": target.get("router_id"),
                "reference_bandwidth": common.get("reference_bandwidth"),
                "passive_default": common.get("passive_default", False),
                "default_originate": common.get("default_originate", False),
                "default_originate_always": common.get("default_originate_always", False),
                "networks": networks,
                "areas": list(areas.values()),
            }
        return {
            "as_number": target.get("as_number"),
            "router_id": target.get("router_id"),
            "bfd_all_interfaces": common.get("bfd_all_interfaces", False),
            "auto_summary": common.get("auto_summary", False),
            "passive_default": common.get("passive_default", False),
            "metric_weights": common.get("metric_weights") or "0 1 0 1 0 0",
            "variance": common.get("variance"),
            "maximum_paths": common.get("maximum_paths"),
            "networks": networks,
            "action_Cfg": "1111111",
        }
