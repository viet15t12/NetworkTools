"""Parse and reconcile EtherChannel operational state from Cisco IOS."""

from __future__ import annotations

import re
from infrastructure.database import sqlcipher as sqlite3
from typing import Any

from .interface_names import normalize_interface_name


def parse_etherchannels(output: str) -> list[dict[str, Any]]:
    """Parse ``show etherchannel summary`` into normalized channel rows.

    The command reveals the protocol but not whether LACP/PAgP was configured
    as active/passive or desirable/auto.  A provisional mode is returned only
    for new rows; reconciliation preserves a compatible mode already in DB.
    """
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?m)^\s*(\d+)\s+Po\d+\(([^)]*)\)\s+(LACP|PAgP|-)\s+(.*)$",
        re.IGNORECASE,
    )
    for match in pattern.finditer(str(output or "")):
        protocol = match.group(3).lower()
        members = re.findall(r"([A-Za-z]+\d+(?:/\d+)*)\([A-Za-z]+\)", match.group(4))
        rows.append(
            {
                "po_number": int(match.group(1)),
                "protocol": "static" if protocol == "-" else protocol,
                "mode": "on" if protocol == "-" else "active" if protocol == "lacp" else "desirable",
                "member_ports": ",".join(normalize_interface_name(item) for item in members),
                "status": "up" if "U" in match.group(2) else "down",
            }
        )
    return rows


def sync_etherchannels(
    conn: sqlite3.Connection, host: str, output: str
) -> None:
    """Upsert observed channels and remove synchronized rows absent on-device."""
    rows = parse_etherchannels(output)
    normalized_output = str(output or "").lower()
    authoritative = bool(rows) or any(
        marker in normalized_output
        for marker in ("number of channel-groups", "no. of channel-groups", "group  port-channel")
    )
    if not authoritative:
        # Missing/unknown output is not proof that every channel was deleted.
        return
    observed: set[int] = set()
    for row in rows:
        observed.add(int(row["po_number"]))
        conn.execute(
            """
            INSERT INTO t06_etherchannel(
                host, po_number, protocol, mode, member_ports, status, success,
                device_present
            ) VALUES (?, ?, ?, ?, ?, ?, 'synchronized', 1)
            ON CONFLICT(host, po_number) DO UPDATE SET protocol = excluded.protocol,
                mode = CASE
                    WHEN t06_etherchannel.protocol = excluded.protocol
                    THEN t06_etherchannel.mode
                    ELSE excluded.mode
                END,
                member_ports = excluded.member_ports, cleanup_member_ports = '',
                status = excluded.status, success = 'synchronized',
                device_present = 1;
            """,
            (
                host,
                row["po_number"],
                row["protocol"],
                row["mode"],
                row["member_ports"],
                row["status"],
            ),
        )

    # An empty, successfully collected summary is authoritative: synchronized
    # rows no longer present on the switch must not remain as false inventory.
    if observed:
        placeholders = ",".join("?" for _ in observed)
        conn.execute(
            f"""
            DELETE FROM t06_etherchannel
            WHERE host = ? AND device_present = 1 AND success = 'synchronized'
              AND po_number NOT IN ({placeholders});
            """,
            (host, *sorted(observed)),
        )
    else:
        conn.execute(
            """
            DELETE FROM t06_etherchannel
            WHERE host = ? AND device_present = 1 AND success = 'synchronized';
            """,
            (host,),
        )


__all__ = ["parse_etherchannels", "sync_etherchannels"]
