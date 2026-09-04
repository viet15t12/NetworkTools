"""SQLite repository for Cisco Syslog configuration state."""

from __future__ import annotations

import re
from contextlib import closing
from ipaddress import ip_address
from pathlib import Path
from typing import Any

from .connections import device_connection, info_connection
from .schema import ensure_device_schema


VALID_PROTOCOLS = {"udp", "tcp"}
INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9./:_-]{0,63}$")


class DeviceStateRepository:
    def __init__(self, device_db: Path, legacy_info_db: Path | None = None) -> None:
        self.device_db = Path(device_db)
        with closing(device_connection(self.device_db)) as conn:
            ensure_device_schema(conn)
        if legacy_info_db is not None:
            self._migrate_legacy_state(Path(legacy_info_db))

    def _migrate_legacy_state(self, info_db: Path) -> None:
        """Copy the old info_collected desired state without deleting it."""
        if not info_db.is_file():
            return
        migration_key = "info_collected.t12_syslog_device_state.v1"
        with closing(device_connection(self.device_db)) as destination:
            migrated = destination.execute(
                "SELECT 1 FROM t10_syslog_migrations WHERE migration_key = ?",
                (migration_key,),
            ).fetchone()
        if migrated is not None:
            return
        with closing(info_connection(info_db)) as source:
            table = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='t12_syslog_device_state'"
            ).fetchone()
            if table is None:
                self._mark_migration_complete(migration_key)
                return
            columns = {
                str(row[1])
                for row in source.execute("PRAGMA table_info(t12_syslog_device_state)")
            }
            select_parts = {
                "device_host": "device_host",
                "server_ip": "server_ip",
                "protocol": "protocol",
                "port": "port",
                "source_interface": (
                    "source_interface" if "source_interface" in columns else "NULL"
                ),
                "trap_severity": (
                    "COALESCE(trap_severity, 5)"
                    if "trap_severity" in columns else "5"
                ),
                "timestamps": (
                    "COALESCE(timestamps, 0)" if "timestamps" in columns else "0"
                ),
                "sequence_numbers": (
                    "COALESCE(sequence_numbers, 0)"
                    if "sequence_numbers" in columns else "0"
                ),
                "configured": (
                    "COALESCE(configured, 0)" if "configured" in columns else "0"
                ),
                "sync_status": (
                    "COALESCE(sync_status, 'synchronized')"
                    if "sync_status" in columns else "'synchronized'"
                ),
                "last_result": "last_result" if "last_result" in columns else "NULL",
                "updated_at": (
                    "COALESCE(updated_at, CURRENT_TIMESTAMP)"
                    if "updated_at" in columns else "CURRENT_TIMESTAMP"
                ),
            }
            names = tuple(select_parts)
            rows = source.execute(
                "SELECT " + ", ".join(select_parts.values())
                + " FROM t12_syslog_device_state"
            ).fetchall()
        placeholders = ", ".join("?" for _ in names)
        with closing(device_connection(self.device_db)) as destination:
            with destination:
                destination.executemany(
                    f"INSERT OR IGNORE INTO t10_syslog_servers "
                    f"({', '.join(names)}) VALUES ({placeholders})",
                    [tuple(row) for row in rows],
                )
                destination.execute(
                    "INSERT OR IGNORE INTO t10_syslog_migrations(migration_key) "
                    "VALUES (?)",
                    (migration_key,),
                )

    def _mark_migration_complete(self, migration_key: str) -> None:
        with closing(device_connection(self.device_db)) as destination:
            destination.execute(
                "INSERT OR IGNORE INTO t10_syslog_migrations(migration_key) VALUES (?)",
                (migration_key,),
            )
            destination.commit()

    def save_device_state(
        self, host: str, server_ip: str, protocol: str, port: int,
        interface: str | None, configured: bool, result: str,
        trap_severity: int = 5, timestamps: bool = False,
        sequence_numbers: bool = False,
    ) -> None:
        with closing(device_connection(self.device_db)) as conn:
            conn.execute(
                """INSERT INTO t10_syslog_servers
                   (device_host, server_ip, protocol, port, source_interface,
                    trap_severity, timestamps, sequence_numbers, configured,
                    sync_status, last_result, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(device_host, server_ip, protocol, port) DO UPDATE SET
                     source_interface=excluded.source_interface,
                     trap_severity=excluded.trap_severity,
                     timestamps=excluded.timestamps,
                     sequence_numbers=excluded.sequence_numbers,
                     configured=excluded.configured,
                     sync_status=excluded.sync_status,
                     last_result=excluded.last_result,
                     updated_at=CURRENT_TIMESTAMP""",
                (
                    host, server_ip, protocol, port, interface, trap_severity,
                    int(timestamps), int(sequence_numbers), int(configured),
                    "synchronized" if configured else "pending_apply", result,
                ),
            )
            conn.commit()

    def save_device_attempt(
        self, host: str, server_ip: str, protocol: str, port: int, result: str,
    ) -> None:
        with closing(device_connection(self.device_db)) as conn:
            conn.execute(
                """INSERT INTO t10_syslog_servers
                   (device_host, server_ip, protocol, port, configured, last_result, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(device_host, server_ip, protocol, port) DO UPDATE SET
                     last_result=excluded.last_result,
                     updated_at=CURRENT_TIMESTAMP""",
                (host, server_ip, protocol, port, result),
            )
            conn.commit()

    def configured_hosts(self, server_ip: str, protocol: str, port: int) -> set[str]:
        with closing(device_connection(self.device_db)) as conn:
            if str(protocol).lower() == "both":
                rows = conn.execute(
                    """SELECT device_host FROM t10_syslog_servers
                       WHERE server_ip = ? AND port = ? AND configured = 1""",
                    (server_ip, port),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT device_host FROM t10_syslog_servers
                       WHERE server_ip = ? AND protocol = ? AND port = ?
                         AND configured = 1""",
                    (server_ip, protocol, port),
                ).fetchall()
        return {str(row["device_host"]) for row in rows}

    @staticmethod
    def _clean_configuration(host: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_host = str(host or "").strip()
        server_ip = str(payload.get("server_ip") or "").strip()
        protocol = str(payload.get("protocol") or "udp").strip().lower()
        source_interface = str(payload.get("source_interface") or "").strip()
        try:
            address = ip_address(server_ip)
        except ValueError as exc:
            raise ValueError("Server IP must be a valid IPv4 or IPv6 address") from exc
        if address.is_unspecified:
            raise ValueError("Server IP cannot be unspecified")
        if not clean_host:
            raise ValueError("Device host is required")
        if protocol not in VALID_PROTOCOLS:
            raise ValueError("Protocol must be UDP or TCP")
        try:
            port = int(payload.get("port", 5514))
            severity = int(payload.get("trap_severity", 5))
        except (TypeError, ValueError) as exc:
            raise ValueError("Port and severity must be numbers") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        if not 0 <= severity <= 7:
            raise ValueError("Trap severity must be between 0 and 7")
        if not source_interface:
            raise ValueError("Source interface is required")
        if not INTERFACE_RE.fullmatch(source_interface):
            raise ValueError("Source interface contains unsupported characters")
        return {
            "device_host": clean_host,
            "server_ip": str(address),
            "protocol": protocol,
            "port": port,
            "source_interface": source_interface,
            "trap_severity": severity,
            "timestamps": bool(payload.get("timestamps", False)),
            "sequence_numbers": bool(payload.get("sequence_numbers", False)),
        }

    def device_configurations(self, host: str) -> list[dict[str, Any]]:
        clean_host = str(host or "").strip()
        if not clean_host:
            return []
        with closing(device_connection(self.device_db)) as conn:
            rows = conn.execute(
                """SELECT device_host, server_ip, protocol, port, source_interface,
                          trap_severity, timestamps, sequence_numbers, configured,
                          sync_status, last_result, updated_at
                   FROM t10_syslog_servers
                   WHERE device_host = ?
                     AND NOT (
                       configured = 0 AND sync_status = 'synchronized'
                       AND source_interface IS NULL
                     )
                   ORDER BY server_ip COLLATE NOCASE, protocol, port""",
                (clean_host,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            row["timestamps"] = bool(row.get("timestamps"))
            row["sequence_numbers"] = bool(row.get("sequence_numbers"))
            row["configured"] = bool(row.get("configured"))
            result.append(row)
        return result

    def save_configuration(
        self, host: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            row = self._clean_configuration(host, payload)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

        original_server = str(
            payload.get("original_server_ip") or row["server_ip"]
        ).strip()
        original_protocol = str(
            payload.get("original_protocol") or row["protocol"]
        ).strip().lower()
        try:
            original_port = int(payload.get("original_port", row["port"]))
        except (TypeError, ValueError):
            original_port = int(row["port"])

        with closing(device_connection(self.device_db)) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                if (
                    original_server != row["server_ip"]
                    or original_protocol != row["protocol"]
                    or original_port != row["port"]
                ):
                    original = conn.execute(
                        """SELECT configured, sync_status
                           FROM t10_syslog_servers
                           WHERE device_host = ? AND server_ip = ?
                             AND protocol = ? AND port = ?""",
                        (
                            row["device_host"], original_server,
                            original_protocol, original_port,
                        ),
                    ).fetchone()
                    if original is not None and (
                        bool(original["configured"])
                        or str(original["sync_status"]) != "pending_apply"
                    ):
                        conn.execute(
                            """UPDATE t10_syslog_servers
                               SET sync_status = 'pending_delete',
                                   updated_at = CURRENT_TIMESTAMP
                               WHERE device_host = ? AND server_ip = ?
                                 AND protocol = ? AND port = ?""",
                            (
                                row["device_host"], original_server,
                                original_protocol, original_port,
                            ),
                        )
                    else:
                        conn.execute(
                            """DELETE FROM t10_syslog_servers
                               WHERE device_host = ? AND server_ip = ?
                                 AND protocol = ? AND port = ?""",
                            (
                                row["device_host"], original_server,
                                original_protocol, original_port,
                            ),
                        )
                conn.execute(
                    """INSERT INTO t10_syslog_servers
                       (device_host, server_ip, protocol, port, source_interface,
                        trap_severity, timestamps, sequence_numbers, configured,
                        sync_status, last_result, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending_apply', NULL,
                               CURRENT_TIMESTAMP)
                       ON CONFLICT(device_host, server_ip, protocol, port) DO UPDATE SET
                         source_interface=excluded.source_interface,
                         trap_severity=excluded.trap_severity,
                         timestamps=excluded.timestamps,
                         sequence_numbers=excluded.sequence_numbers,
                         sync_status='pending_apply',
                         last_result=NULL,
                         updated_at=CURRENT_TIMESTAMP""",
                    (
                        row["device_host"], row["server_ip"], row["protocol"],
                        row["port"], row["source_interface"], row["trap_severity"],
                        int(row["timestamps"]), int(row["sequence_numbers"]),
                    ),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                return {"ok": False, "message": f"Could not save Syslog server: {exc}"}
        return {"ok": True, "message": "Syslog server configuration saved."}

    def stage_delete_configuration(
        self, host: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        clean_host = str(host or "").strip()
        server_ip = str(payload.get("server_ip") or "").strip()
        protocol = str(payload.get("protocol") or "udp").strip().lower()
        try:
            port = int(payload.get("port", 5514))
        except (TypeError, ValueError):
            return {"ok": False, "message": "Port must be a number"}
        with closing(device_connection(self.device_db)) as conn:
            row = conn.execute(
                """SELECT configured, sync_status FROM t10_syslog_servers
                   WHERE device_host = ? AND server_ip = ? AND protocol = ? AND port = ?""",
                (clean_host, server_ip, protocol, port),
            ).fetchone()
            if row is None:
                return {"ok": False, "message": "Syslog server configuration no longer exists."}
            if not bool(row["configured"]) and str(row["sync_status"]) == "pending_apply":
                conn.execute(
                    """DELETE FROM t10_syslog_servers
                       WHERE device_host = ? AND server_ip = ? AND protocol = ? AND port = ?""",
                    (clean_host, server_ip, protocol, port),
                )
                message = "Unapplied Syslog server configuration deleted."
            else:
                conn.execute(
                    """UPDATE t10_syslog_servers
                       SET sync_status = 'pending_delete', updated_at = CURRENT_TIMESTAMP
                       WHERE device_host = ? AND server_ip = ? AND protocol = ? AND port = ?""",
                    (clean_host, server_ip, protocol, port),
                )
                message = "Syslog server marked for removal. Use View & Push to apply."
            conn.commit()
        return {"ok": True, "message": message}

    def delete_configuration_record(
        self, host: str, server_ip: str, protocol: str, port: int
    ) -> None:
        with closing(device_connection(self.device_db)) as conn:
            conn.execute(
                """DELETE FROM t10_syslog_servers
                   WHERE device_host = ? AND server_ip = ? AND protocol = ? AND port = ?""",
                (host, server_ip, protocol, int(port)),
            )
            conn.commit()


__all__ = ["DeviceStateRepository"]
