"""Parse and synchronize bounded Cisco switch operational snapshots."""

from __future__ import annotations

import re
from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .etherchannel_sync import parse_etherchannels, sync_etherchannels
from .interface_names import INTERFACE_NAME_PATTERN, normalize_interface_name
from features.devices.sync import (
    clear_fhrp_members,
    insert_fhrp_members,
    parse_running_config_sections,
)


def parse_vlan_brief(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(?m)^\s*(\d+)\s+(\S+)\s+(active|suspended|suspend)\b",
        str(output or ""),
        re.IGNORECASE,
    ):
        vlan_id = int(match.group(1))
        if 1002 <= vlan_id <= 1005:
            continue
        rows.append(
            {
                "vlan_id": vlan_id,
                "vlan_name": match.group(2),
                "state": "suspend" if "suspend" in match.group(3).lower() else "active",
            }
        )
    return rows


def parse_interface_status(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        rf"(?m)^\s*({INTERFACE_NAME_PATTERN})\s+(.*?)\s+"
        r"(connected|notconnect|disabled|err-disabled)\s+"
        r"(trunk|routed|unassigned|\d+)\s+"
        r"(auto|a-full|full|a-half|half)\s+(auto|a-\d+|\d+)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(str(output or "")):
        vlan = match.group(4).lower()
        rows.append(
            {
                "if_name": normalize_interface_name(match.group(1)),
                "description": match.group(2).strip(),
                "mode": "trunk" if vlan == "trunk" else "routed" if vlan == "routed" else "access",
                "admin_status": "down" if match.group(3).lower() == "disabled" else "up",
                "oper_status": (
                    "up" if match.group(3).lower() == "connected"
                    else "err-disabled" if match.group(3).lower() == "err-disabled"
                    else "down"
                ),
                "speed": match.group(6).lower().removeprefix("a-"),
                "duplex": match.group(5).lower().removeprefix("a-"),
                "access_vlan": int(vlan) if vlan.isdigit() else None,
            }
        )
    return rows


def parse_trunks(output: str) -> dict[str, dict[str, Any]]:
    trunks: dict[str, dict[str, Any]] = {}
    text = str(output or "")
    pattern = re.compile(
        rf"(?m)^\s*({INTERFACE_NAME_PATTERN})\s+\S+\s+"
        r"(802\.1q|isl|n-802\.1q|n-isl)\s+trunking\s+(\d+)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        encapsulation = "dot1q" if "802.1q" in match.group(2).lower() else "isl"
        trunks[normalize_interface_name(match.group(1))] = {
            "native_vlan": int(match.group(3)),
            "encapsulation": encapsulation,
            "allowed_vlans": "all",
        }
    allowed_section = re.search(
        r"(?ims)^\s*Port\s+Vlans allowed on trunk\s*$"
        r"(.*?)(?=^\s*Port\s+Vlans |\Z)",
        text,
    )
    if allowed_section:
        allowed_pattern = re.compile(
            rf"(?m)^\s*({INTERFACE_NAME_PATTERN})\s+"
            r"(all|none|\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)\s*$",
            re.IGNORECASE,
        )
        for match in allowed_pattern.finditer(allowed_section.group(1)):
            if_name = normalize_interface_name(match.group(1))
            if if_name in trunks:
                trunks[if_name]["allowed_vlans"] = match.group(2).lower()
    return trunks


def parse_vtp_status(output: str) -> dict[str, Any] | None:
    text = str(output or "")
    domain = re.search(r"VTP Domain Name\s*:\s*(\S+)", text, re.IGNORECASE)
    if not domain or domain.group(1).lower() in {"null", "none", "(none)"}:
        return None
    version = re.search(r"VTP version running\s*:\s*(\d+)", text, re.IGNORECASE)
    mode = re.search(r"VTP Operating Mode\s*:\s*(\w+)", text, re.IGNORECASE)
    pruning = re.search(r"VTP Pruning Mode\s*:\s*(\w+)", text, re.IGNORECASE)
    return {
        "domain_name": domain.group(1).strip(),
        "version": int(version.group(1)) if version else 2,
        "mode": mode.group(1).lower() if mode else "transparent",
        "pruning": int(bool(pruning and pruning.group(1).lower() == "enabled")),
        "primary_server": int(bool(re.search(r"VTP Primary Server\s*:\s*local", text, re.IGNORECASE))),
    }


@dataclass
class _Database:
    db_path: str

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _module_has_local_state(conn: sqlite3.Connection, host: str, module: str) -> bool:
    table = {"vlan": "t06_vlan_db", "interfaces": "t06_interface_l2", "vtp": "t09_vtp_switches"}[module]
    return conn.execute(f"SELECT 1 FROM {table} WHERE host = ? LIMIT 1", (host,)).fetchone() is not None


def _module_is_pending(db: _Database, host: str, module: str) -> bool:
    tables = {
        "vlan": ("t06_vlan_db",),
        "interfaces": ("t06_interface_l2", "t06_etherchannel"),
        "vtp": ("t09_vtp_switches",),
    }[module]
    with closing(db._connect()) as conn:
        return any(
            conn.execute(
                f"""
                SELECT 1 FROM {table}
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                ) LIMIT 1;
                """,
                (host,),
            ).fetchone() is not None
            for table in tables
        )


def _sync_vlans(conn: sqlite3.Connection, host: str, rows: list[dict[str, Any]]) -> int:
    # A collected VLAN table is authoritative for device presence. Keep rows
    # that may still be referenced by local policy, but make absent VLANs
    # invisible as device state until a later snapshot advertises them again.
    conn.execute(
        """
        UPDATE t06_vlan_db
        SET success = 'synchronized', device_present = 0
        WHERE host = ?;
        """,
        (host,),
    )
    for row in rows:
        conn.execute(
            """
            INSERT INTO t06_vlan_db(
                host, vlan_id, vlan_name, state, success, device_present
            )
            VALUES (?, ?, ?, ?, 'synchronized', 1)
            ON CONFLICT(host, vlan_id) DO UPDATE SET
                vlan_name = excluded.vlan_name, state = excluded.state,
                success = 'synchronized', device_present = 1
            """,
            (host, row["vlan_id"], row["vlan_name"], row["state"]),
        )
    return len(rows)


def _sync_interfaces(conn: sqlite3.Connection, host: str, snapshot: dict[str, str]) -> int:
    rows = parse_interface_status(snapshot.get("interfaces_status", ""))
    trunks = parse_trunks(snapshot.get("interfaces_trunk", ""))
    synchronized_names: set[str] = set()
    for row in rows:
        # ``show interfaces trunk`` is authoritative for trunk mode. Some IOS
        # variants report a Port-channel's access/native VLAN number in
        # ``show interfaces status`` even while the logical interface is
        # actively trunking.
        trunk = trunks.get(row["if_name"])
        if trunk is not None:
            row["mode"] = "trunk"
            row["access_vlan"] = None
        conn.execute(
            """
            INSERT INTO t06_interface_l2(
                host, if_name, description, mode, admin_status, oper_status,
                speed, duplex, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synchronized')
            ON CONFLICT(host, if_name) DO UPDATE SET
                description = excluded.description, mode = excluded.mode,
                admin_status = excluded.admin_status, oper_status = excluded.oper_status,
                speed = excluded.speed, duplex = excluded.duplex,
                updated_at = datetime('now'), success = 'synchronized'
            """,
            (host, row["if_name"], row["description"], row["mode"], row["admin_status"],
             row["oper_status"], row["speed"] if row["speed"] in {"auto", "10", "100", "1000", "10000"} else "auto",
             row["duplex"] if row["duplex"] in {"auto", "full", "half"} else "auto"),
        )
        iface_id = conn.execute(
            "SELECT id FROM t06_interface_l2 WHERE host = ? AND if_name = ?", (host, row["if_name"])
        ).fetchone()[0]
        synchronized_names.add(row["if_name"])
        if row["mode"] == "access" and row["access_vlan"] is not None:
            conn.execute("DELETE FROM t06_iface_trunk WHERE iface_id = ?", (iface_id,))
            conn.execute(
                "INSERT INTO t06_iface_access(iface_id, access_vlan) VALUES (?, ?) "
                "ON CONFLICT(iface_id) DO UPDATE SET access_vlan = excluded.access_vlan",
                (iface_id, row["access_vlan"]),
            )
        elif row["mode"] == "trunk":
            conn.execute("DELETE FROM t06_iface_access WHERE iface_id = ?", (iface_id,))
            if trunk is not None:
                conn.execute(
                    """
                    INSERT INTO t06_iface_trunk(iface_id, allowed_vlans, native_vlan, encapsulation)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(iface_id) DO UPDATE SET allowed_vlans = excluded.allowed_vlans,
                        native_vlan = excluded.native_vlan, encapsulation = excluded.encapsulation
                    """,
                    (iface_id, trunk["allowed_vlans"], trunk["native_vlan"], trunk["encapsulation"]),
                )

    # Keep a trunk visible even when a platform omits the logical
    # Port-channel from ``show interfaces status``. The trunk table still
    # provides an authoritative interface name and mode.
    for if_name, trunk in trunks.items():
        if if_name in synchronized_names:
            continue
        conn.execute(
            """
            INSERT INTO t06_interface_l2(host, if_name, mode, success)
            VALUES (?, ?, 'trunk', 'synchronized')
            ON CONFLICT(host, if_name) DO UPDATE SET
                mode = 'trunk', updated_at = datetime('now'),
                success = 'synchronized'
            """,
            (host, if_name),
        )
        iface_id = conn.execute(
            "SELECT id FROM t06_interface_l2 WHERE host = ? AND if_name = ?",
            (host, if_name),
        ).fetchone()[0]
        conn.execute("DELETE FROM t06_iface_access WHERE iface_id = ?", (iface_id,))
        conn.execute(
            """
            INSERT INTO t06_iface_trunk(iface_id, allowed_vlans, native_vlan, encapsulation)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(iface_id) DO UPDATE SET allowed_vlans = excluded.allowed_vlans,
                native_vlan = excluded.native_vlan, encapsulation = excluded.encapsulation
            """,
            (iface_id, trunk["allowed_vlans"], trunk["native_vlan"], trunk["encapsulation"]),
        )
    sync_etherchannels(conn, host, snapshot.get("etherchannel_summary", ""))
    return len(synchronized_names | set(trunks))


def _sync_vtp(conn: sqlite3.Connection, host: str, output: str) -> int:
    row = parse_vtp_status(output)
    if row is None:
        return 0
    conn.execute(
        """
        INSERT INTO t09_vtp_domains(domain_name, version, password_type, password_value)
        VALUES (?, ?, 'none', NULL)
        ON CONFLICT(domain_name) DO UPDATE SET version = excluded.version
        """,
        (row["domain_name"], row["version"]),
    )
    domain_id = conn.execute(
        "SELECT vtp_domain_id FROM t09_vtp_domains WHERE domain_name = ?", (row["domain_name"],)
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO t09_vtp_switches(
            vtp_domain_id, host, pruning, sync_status, success
        ) VALUES (?, ?, ?, 'synchronized', 'synchronized')
        ON CONFLICT(host) DO UPDATE SET vtp_domain_id = excluded.vtp_domain_id,
            pruning = excluded.pruning, sync_status = 'synchronized',
            success = 'synchronized'
        """,
        (domain_id, host, row["pruning"]),
    )
    switch_id = conn.execute(
        "SELECT vtp_switch_id FROM t09_vtp_switches WHERE host = ?", (host,)
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO t09_vtp_database_modes(vtp_switch_id, database_type, mode, primary_server)
        VALUES (?, 'vlan', ?, ?)
        ON CONFLICT(vtp_switch_id, database_type) DO UPDATE SET
            mode = excluded.mode, primary_server = excluded.primary_server
        """,
        (switch_id, row["mode"], row["primary_server"]),
    )
    return 1


def sync_switch_state(
    db_path: str | Path,
    host: str,
    snapshot: dict[str, str],
    mode: str = "safe",
) -> dict[str, Any]:
    """Preview or merge switch state while preserving unpushed local modules."""
    db = _Database(str(db_path))
    from .schema import ensure_switch_schema

    ensure_switch_schema(db)
    parsed_fhrp = parse_running_config_sections(snapshot.get("running_config", ""))
    modules = {
        "vlan": bool(parse_vlan_brief(snapshot.get("vlan_brief", ""))),
        "interfaces": bool(parse_interface_status(snapshot.get("interfaces_status", ""))),
        "vtp": parse_vtp_status(snapshot.get("vtp_status", "")) is not None,
        "fhrp": "running_config" in snapshot,
    }
    conflicts: list[str] = []
    with db._connect() as conn:
        for module, available in modules.items():
            if not available:
                continue
            if module == "fhrp":
                pending = conn.execute(
                    """
                    SELECT 1 FROM t08_fhrp_members AS m
                    LEFT JOIN t08_fhrp_tracks AS t ON t.member_id = m.member_id
                    WHERE m.host = ? AND (
                        m.sync_status IN ('pending_apply', 'pending_delete')
                        OR t.sync_status IN ('pending_apply', 'pending_delete')
                    ) LIMIT 1;
                    """,
                    (host,),
                ).fetchone()
                if pending is not None:
                    conflicts.append(module)
                continue
            if _module_has_local_state(conn, host, module) and _module_is_pending(db, host, module):
                conflicts.append(module)
    if mode == "preview":
        return {"conflicts": conflicts, "available": [key for key, value in modules.items() if value]}

    counts = {"vlans": 0, "interfaces": 0, "vtp": 0, "fhrp_members": 0}
    applied: list[str] = []
    with db._connect() as conn, conn:
        if modules["vlan"] and (mode == "force_device_state" or "vlan" not in conflicts):
            counts["vlans"] = _sync_vlans(conn, host, parse_vlan_brief(snapshot["vlan_brief"]))
            applied.append("vlan")
        if modules["interfaces"] and (mode == "force_device_state" or "interfaces" not in conflicts):
            counts["interfaces"] = _sync_interfaces(conn, host, snapshot)
            applied.append("interfaces")
        if modules["vtp"] and (mode == "force_device_state" or "vtp" not in conflicts):
            counts["vtp"] = _sync_vtp(conn, host, snapshot["vtp_status"])
            applied.append("vtp")
        if modules["fhrp"] and (mode == "force_device_state" or "fhrp" not in conflicts):
            clear_fhrp_members(conn, host)
            insert_fhrp_members(conn, host, parsed_fhrp.fhrp_members)
            counts["fhrp_members"] = len(parsed_fhrp.fhrp_members)
            applied.append("fhrp")
    return {**counts, "conflicts": conflicts, "applied": applied}
