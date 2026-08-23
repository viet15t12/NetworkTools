"""Hot-path SQLite repository for Syslog messages and retention."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any

from ..domain.models import SyslogMessage
from .connections import info_connection
from .schema import ensure_schema


class MessageRepository:
    def __init__(self, info_db: Path) -> None:
        self.info_db = Path(info_db)
        with closing(info_connection(self.info_db)) as conn:
            ensure_schema(conn)

    def insert_messages(self, messages: Iterable[SyslogMessage]) -> list[dict[str, Any]]:
        rows = list(messages)
        if not rows:
            return []
        sql = """INSERT INTO t12_syslog_messages
            (device_host, source_ip, device_time, sequence_number,
             clock_unsynchronized, received_at, syslog_pri, syslog_facility,
             cisco_facility, cisco_subfacility, facility, severity, mnemonic,
             message, raw_message, protocol, parse_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        values = [(
            row.device_host, row.source_ip, row.device_time, row.sequence_number,
            int(row.clock_unsynchronized), row.received_at, row.syslog_pri,
            row.syslog_facility, row.cisco_facility, row.cisco_subfacility,
            row.facility, row.severity, row.mnemonic, row.message,
            row.raw_message, row.protocol, row.parse_status,
        ) for row in rows]
        with closing(info_connection(self.info_db)) as conn:
            conn.executemany(sql, values)
            last_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        first_id = max(1, last_id - len(rows) + 1) if last_id else 0
        result: list[dict[str, Any]] = []
        for offset, row in enumerate(rows):
            item = row.to_dict()
            item["id"] = first_id + offset if first_id else 0
            result.append(item)
        return result

    def query_messages(
        self, filters: dict[str, Any], before_id: int = 0, limit: int = 200
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        host = str(filters.get("host") or "").strip()
        search = str(filters.get("search") or "").strip()
        severities = self._valid_severities(filters.get("severities", []))
        protocols = self._valid_protocols(filters.get("protocols", []))
        if host:
            clauses.append("device_host = ?")
            params.append(host)
        if search:
            clauses.append(
                "(message LIKE ? ESCAPE '\\' OR mnemonic LIKE ? ESCAPE '\\' "
                "OR cisco_facility LIKE ? ESCAPE '\\')"
            )
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend((f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"))
        if severities:
            clauses.append(f"severity IN ({','.join('?' for _ in severities)})")
            params.extend(severities)
        if protocols:
            clauses.append(f"protocol IN ({','.join('?' for _ in protocols)})")
            params.extend(protocols)
        if before_id > 0:
            clauses.append("id < ?")
            params.append(before_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(max(1, min(int(limit), 500)))
        with closing(info_connection(self.info_db)) as conn:
            rows = conn.execute(
                "SELECT * FROM t12_syslog_messages" + where + " ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._public_row(dict(row)) for row in rows]

    @staticmethod
    def _public_row(row: dict[str, Any]) -> dict[str, Any]:
        row["clock_unsynchronized"] = bool(row.get("clock_unsynchronized"))
        row["facility"] = row.get("cisco_facility") or (
            str(row["syslog_facility"]) if row.get("syslog_facility") is not None else row.get("facility")
        )
        return row

    @staticmethod
    def _valid_severities(values: Any) -> list[int]:
        result: list[int] = []
        for value in values or []:
            try:
                severity = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= severity <= 7 and severity not in result:
                result.append(severity)
        return result

    @staticmethod
    def _valid_protocols(values: Any) -> list[str]:
        result: list[str] = []
        for value in values or []:
            protocol = str(value or "").strip().lower()
            if protocol in {"udp", "tcp"} and protocol not in result:
                result.append(protocol)
        return result

    def delete_expired(self, retention_days: int, batch_size: int = 5_000) -> int:
        total = 0
        modifier = f"-{max(1, int(retention_days))} days"
        batch_size = max(100, min(int(batch_size), 10_000))
        with closing(info_connection(self.info_db)) as conn:
            while True:
                cursor = conn.execute(
                    """DELETE FROM t12_syslog_messages WHERE id IN (
                         SELECT id FROM t12_syslog_messages
                         WHERE received_at < datetime('now', ?) LIMIT ?
                       )""",
                    (modifier, batch_size),
                )
                conn.commit()
                deleted = max(0, int(cursor.rowcount))
                total += deleted
                if deleted < batch_size:
                    break
        return total


__all__ = ["MessageRepository"]
