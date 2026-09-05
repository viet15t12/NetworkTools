"""Multi-switch VTP desired-state persistence modeled after Routing Group."""

from __future__ import annotations

import re
from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any

from .schema import ensure_switch_schema


VTP_MODES = {"server", "client", "transparent", "off"}


class VtpGroupRepository:
    """Own VTP group SQL and isolate one member failure from later switches."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def connected_switches(self) -> list[dict[str, str]]:
        with closing(self.db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT host, device_name
                FROM t01_devices
                WHERE connection_status = 'connected'
                  AND (
                    lower(COALESCE(role, '')) IN ('sw2', 'sw3')
                    OR lower(COALESCE(device_type, '')) IN ('switch', 'sw2', 'sw3')
                  )
                ORDER BY host COLLATE NOCASE;
                """
            ).fetchall()
        return [
            {"host": str(row["host"]), "device_name": str(row["device_name"] or "")}
            for row in rows
        ]

    def list_groups(self) -> list[dict[str, Any]]:
        with closing(self.db._connect()) as conn:
            domains = conn.execute(
                """
                SELECT vtp_domain_id, domain_name, version, description, updated_at
                FROM t09_vtp_domains
                ORDER BY updated_at DESC, domain_name COLLATE NOCASE;
                """
            ).fetchall()
            result: list[dict[str, Any]] = []
            for domain in domains:
                item = dict(domain)
                item["members"] = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT s.vtp_switch_id, s.host, s.pruning, s.sync_status,
                               s.success, m.mode
                        FROM t09_vtp_switches AS s
                        LEFT JOIN t09_vtp_database_modes AS m
                          ON m.vtp_switch_id = s.vtp_switch_id
                         AND m.database_type = 'vlan'
                        WHERE s.vtp_domain_id = ?
                        ORDER BY s.host COLLATE NOCASE;
                        """,
                        (domain["vtp_domain_id"],),
                    ).fetchall()
                ]
                result.append(item)
        return result

    def save_group(
        self, domain: dict[str, Any], members: list[dict[str, Any]]
    ) -> dict[str, Any]:
        eligible_hosts = {row["host"] for row in self.connected_switches()}
        successful: list[str] = []
        failed: list[dict[str, str]] = []
        eligible_members: list[dict[str, Any]] = []
        for member in members:
            host = str(member["host"])
            if host not in eligible_hosts:
                failed.append(
                    {"host": host, "reason": "Host is not a connected switch"}
                )
            else:
                eligible_members.append(member)

        domain_id = self._save_domain(domain) if eligible_members else 0
        for member in eligible_members:
            host = str(member["host"])
            try:
                self._save_member(domain_id, member)
                successful.append(host)
            except (sqlite3.Error, ValueError) as exc:
                failed.append({"host": host, "reason": str(exc)})
        message = (
            f"VTP Group saved: {len(successful)} succeeded, {len(failed)} failed."
        )
        if failed:
            message += " Failed switches: " + "; ".join(
                f"{row['host']}: {row['reason']}" for row in failed
            )
            message += "."
        return {
            "ok": bool(successful) and not failed,
            "partial": bool(successful) and bool(failed),
            "vtp_domain_id": domain_id,
            "successful": successful,
            "failed": failed,
            "message": message,
        }

    def _save_domain(self, domain: dict[str, Any]) -> int:
        with closing(self.db._connect()) as conn:
            with conn:
                existing = conn.execute(
                    """
                    SELECT password_type
                    FROM t09_vtp_domains
                    WHERE domain_name = ?
                    LIMIT 1;
                    """,
                    (domain["domain_name"],),
                ).fetchone()
                if existing is not None and existing["password_type"] != "none":
                    raise ValueError(
                        "An authenticated VTP domain cannot be changed by VTP Group"
                    )
                conn.execute(
                    """
                    INSERT INTO t09_vtp_domains (
                        domain_name, version, password_type, password_value, description
                    ) VALUES (?, ?, 'none', NULL, ?)
                    ON CONFLICT(domain_name) DO UPDATE SET
                        version = excluded.version,
                        description = excluded.description;
                    """,
                    (
                        domain["domain_name"],
                        domain["version"],
                        domain.get("description") or None,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT vtp_domain_id FROM t09_vtp_domains
                    WHERE domain_name = ? LIMIT 1;
                    """,
                    (domain["domain_name"],),
                ).fetchone()
                if row is None:
                    raise ValueError("VTP domain could not be saved")
                domain_id = int(row["vtp_domain_id"])
                # Domain/version changes affect every existing member.
                conn.execute(
                    """
                    UPDATE t09_vtp_switches
                    SET sync_status = 'pending_apply', success = 'pending_apply'
                    WHERE vtp_domain_id = ?;
                    """,
                    (domain_id,),
                )
        return domain_id

    def _save_member(self, domain_id: int, member: dict[str, Any]) -> None:
        host = str(member["host"])
        with closing(self.db._connect()) as conn:
            with conn:
                inventory = conn.execute(
                    """
                    SELECT 1 FROM t01_devices
                    WHERE host = ? AND connection_status = 'connected'
                      AND (
                        lower(COALESCE(role, '')) IN ('sw2', 'sw3')
                        OR lower(COALESCE(device_type, ''))
                           IN ('switch', 'sw2', 'sw3')
                      )
                    LIMIT 1;
                    """,
                    (host,),
                ).fetchone()
                if inventory is None:
                    raise ValueError("Host is not a connected switch")
                unsupported = conn.execute(
                    """
                    SELECT 1
                    FROM t09_vtp_switches AS s
                    JOIN t09_vtp_database_modes AS m
                      ON m.vtp_switch_id = s.vtp_switch_id
                    WHERE s.host = ?
                      AND (m.database_type != 'vlan' OR m.primary_server = 1)
                    LIMIT 1;
                    """,
                    (host,),
                ).fetchone()
                if unsupported is not None:
                    raise ValueError(
                        "VTPv3 MST/primary state requires the interactive workflow"
                    )
                previous = conn.execute(
                    """
                    SELECT vtp_domain_id
                    FROM t09_vtp_switches
                    WHERE host = ?
                    LIMIT 1;
                    """,
                    (host,),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO t09_vtp_switches (
                        vtp_domain_id, host, pruning, sync_status, success
                    ) VALUES (?, ?, ?, 'pending_apply', 'pending_apply')
                    ON CONFLICT(host) DO UPDATE SET
                        vtp_domain_id = excluded.vtp_domain_id,
                        pruning = excluded.pruning,
                        sync_status = 'pending_apply',
                        success = 'pending_apply';
                    """,
                    (domain_id, host, int(bool(member.get("pruning")))),
                )
                switch = conn.execute(
                    """
                    SELECT vtp_switch_id FROM t09_vtp_switches
                    WHERE host = ? LIMIT 1;
                    """,
                    (host,),
                ).fetchone()
                if switch is None:
                    raise ValueError("VTP switch membership could not be saved")
                conn.execute(
                    """
                    INSERT INTO t09_vtp_database_modes (
                        vtp_switch_id, database_type, mode, primary_server
                    ) VALUES (?, 'vlan', ?, 0)
                    ON CONFLICT(vtp_switch_id, database_type) DO UPDATE SET
                        mode = excluded.mode,
                        primary_server = 0;
                    """,
                    (int(switch["vtp_switch_id"]), member["mode"]),
                )
                if previous is not None and int(previous["vtp_domain_id"]) != domain_id:
                    conn.execute(
                        """
                        DELETE FROM t09_vtp_domains
                        WHERE vtp_domain_id = ?
                          AND NOT EXISTS (
                              SELECT 1 FROM t09_vtp_switches
                              WHERE vtp_domain_id = ?
                          );
                        """,
                        (
                            int(previous["vtp_domain_id"]),
                            int(previous["vtp_domain_id"]),
                        ),
                    )


class VtpGroupService:
    """Validate a VTP domain and stage it independently for up to five switches."""

    MAX_HOSTS = 5

    def __init__(self, db: Any) -> None:
        self.db = db
        ensure_switch_schema(db)
        self.repository = VtpGroupRepository(db)

    def options(self) -> dict[str, Any]:
        return {"ok": True, "hosts": self.repository.connected_switches()}

    def groups(self) -> dict[str, Any]:
        return {"ok": True, "groups": self.repository.list_groups()}

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            domain, members = self._normalize(payload)
            return self.repository.save_group(domain, members)
        except (sqlite3.Error, ValueError) as exc:
            return {
                "ok": False,
                "partial": False,
                "vtp_domain_id": 0,
                "successful": [],
                "failed": [],
                "message": str(exc),
            }

    def _normalize(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        domain_name = str(payload.get("domain_name") or "").strip()
        if not 1 <= len(domain_name) <= 32:
            raise ValueError("VTP domain name must contain 1 to 32 characters.")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", domain_name) is None:
            raise ValueError(
                "VTP domain name may only contain letters, numbers, dots, dashes and underscores."
            )
        version = self.db._int_or_none(payload.get("version"))
        if version not in {1, 2, 3}:
            raise ValueError("VTP version must be 1, 2 or 3.")
        raw_members = [
            self.db._as_dict(value)
            for value in self.db._as_list(payload.get("members"))
        ]
        if len(raw_members) < 2:
            raise ValueError("VTP Group requires at least two selected switches.")
        if len(raw_members) > self.MAX_HOSTS:
            raise ValueError(
                f"VTP Group supports at most {self.MAX_HOSTS} selected switches."
            )
        seen: set[str] = set()
        members: list[dict[str, Any]] = []
        for raw in raw_members:
            host = str(raw.get("host") or "").strip()
            mode = str(raw.get("mode") or "client").strip().lower()
            if not host or host in seen:
                raise ValueError("Every VTP member must use a unique switch host.")
            if mode not in VTP_MODES:
                raise ValueError(f"Unsupported VTP mode on {host}: {mode}.")
            seen.add(host)
            members.append(
                {
                    "host": host,
                    "mode": mode,
                    "pruning": bool(raw.get("pruning")),
                }
            )
        return (
            {
                "domain_name": domain_name,
                "version": version,
                "description": str(payload.get("description") or "").strip(),
            },
            members,
        )


__all__ = ["VtpGroupRepository", "VtpGroupService"]
