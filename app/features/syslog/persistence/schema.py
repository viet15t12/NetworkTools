"""Non-destructive schema and migration helpers for existing workspaces."""

from __future__ import annotations

import sqlite3


SYSLOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS t12_syslog_messages (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    device_host          TEXT NOT NULL,
    source_ip            TEXT NOT NULL,
    device_time          TEXT,
    sequence_number      INTEGER,
    clock_unsynchronized INTEGER NOT NULL DEFAULT 0 CHECK (clock_unsynchronized IN (0, 1)),
    received_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    syslog_pri           INTEGER CHECK (syslog_pri BETWEEN 0 AND 191),
    syslog_facility      INTEGER CHECK (syslog_facility BETWEEN 0 AND 23),
    cisco_facility       TEXT,
    cisco_subfacility    TEXT,
    facility             TEXT,
    severity             INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 7),
    mnemonic             TEXT,
    message              TEXT NOT NULL,
    raw_message          TEXT,
    protocol             TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    parse_status         TEXT NOT NULL DEFAULT 'parsed'
                         CHECK (parse_status IN ('parsed', 'partial', 'raw'))
);

CREATE INDEX IF NOT EXISTS idx_t12_syslog_host_time
    ON t12_syslog_messages(device_host, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_t12_syslog_severity_time
    ON t12_syslog_messages(severity, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_t12_syslog_source_ip
    ON t12_syslog_messages(source_ip);
"""

SYSLOG_DEVICE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS t10_syslog_servers (
    device_host       TEXT NOT NULL,
    server_ip         TEXT NOT NULL,
    protocol          TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    port              INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    source_interface  TEXT,
    trap_severity     INTEGER NOT NULL DEFAULT 5 CHECK (trap_severity BETWEEN 0 AND 7),
    timestamps        INTEGER NOT NULL DEFAULT 0 CHECK (timestamps IN (0, 1)),
    sequence_numbers  INTEGER NOT NULL DEFAULT 0 CHECK (sequence_numbers IN (0, 1)),
    configured        INTEGER NOT NULL DEFAULT 0 CHECK (configured IN (0, 1)),
    sync_status       TEXT NOT NULL DEFAULT 'synchronized'
                      CHECK (sync_status IN ('pending_apply', 'synchronized', 'pending_delete')),
    last_result       TEXT,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_host, server_ip, protocol, port),
    FOREIGN KEY (device_host) REFERENCES t01_devices(host)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_t10_syslog_servers_host
    ON t10_syslog_servers(device_host);

CREATE TABLE IF NOT EXISTS t10_syslog_migrations (
    migration_key  TEXT PRIMARY KEY,
    completed_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

MESSAGE_COLUMNS = {
    "sequence_number": "INTEGER",
    "clock_unsynchronized": "INTEGER NOT NULL DEFAULT 0 CHECK (clock_unsynchronized IN (0, 1))",
    "syslog_pri": "INTEGER CHECK (syslog_pri BETWEEN 0 AND 191)",
    "syslog_facility": "INTEGER CHECK (syslog_facility BETWEEN 0 AND 23)",
    "cisco_facility": "TEXT",
    "cisco_subfacility": "TEXT",
    "facility": "TEXT",
}

DEVICE_CONFIG_COLUMNS = {
    "source_interface": "TEXT",
    "trap_severity": "INTEGER NOT NULL DEFAULT 5 CHECK (trap_severity BETWEEN 0 AND 7)",
    "timestamps": "INTEGER NOT NULL DEFAULT 0 CHECK (timestamps IN (0, 1))",
    "sequence_numbers": "INTEGER NOT NULL DEFAULT 0 CHECK (sequence_numbers IN (0, 1))",
    "configured": "INTEGER NOT NULL DEFAULT 0 CHECK (configured IN (0, 1))",
    "sync_status": (
        "TEXT NOT NULL DEFAULT 'synchronized' "
        "CHECK (sync_status IN ('pending_apply', 'synchronized', 'pending_delete'))"
    ),
    "last_result": "TEXT",
    "updated_at": "TEXT",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SYSLOG_SCHEMA_SQL)
    existing = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(t12_syslog_messages)")
    }
    for name, declaration in MESSAGE_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE t12_syslog_messages ADD COLUMN {name} {declaration}")
    conn.execute(
        """UPDATE t12_syslog_messages SET cisco_facility = facility
           WHERE cisco_facility IS NULL AND facility IS NOT NULL
             AND facility GLOB '*[^0-9]*'"""
    )
    conn.execute(
        """UPDATE t12_syslog_messages
           SET syslog_facility = CAST(facility AS INTEGER),
               syslog_pri = CAST(facility AS INTEGER) * 8 + severity
           WHERE syslog_facility IS NULL AND facility IS NOT NULL
             AND facility NOT GLOB '*[^0-9]*'
             AND CAST(facility AS INTEGER) BETWEEN 0 AND 23"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_t12_syslog_cisco_facility_time
           ON t12_syslog_messages(cisco_facility, received_at DESC)"""
    )
    conn.commit()


def ensure_device_schema(conn: sqlite3.Connection) -> None:
    """Create/upgrade desired Syslog configuration in device_network.db."""
    conn.executescript(SYSLOG_DEVICE_SCHEMA_SQL)
    existing = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(t10_syslog_servers)")
    }
    for name, declaration in DEVICE_CONFIG_COLUMNS.items():
        if name not in existing:
            conn.execute(
                f"ALTER TABLE t10_syslog_servers ADD COLUMN {name} {declaration}"
            )
    conn.commit()


__all__ = [
    "SYSLOG_DEVICE_SCHEMA_SQL",
    "SYSLOG_SCHEMA_SQL",
    "ensure_device_schema",
    "ensure_schema",
]
