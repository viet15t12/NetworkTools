-- Only received Syslog events are stored in info_collected.db.
PRAGMA journal_mode = WAL;

CREATE TABLE t12_syslog_messages (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    device_host          TEXT NOT NULL,
    source_ip            TEXT NOT NULL,
    device_time          TEXT,
    sequence_number      INTEGER,
    clock_unsynchronized INTEGER NOT NULL DEFAULT 0
                         CHECK (clock_unsynchronized IN (0, 1)),
    received_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    syslog_pri           INTEGER CHECK (syslog_pri BETWEEN 0 AND 191),
    syslog_facility      INTEGER CHECK (syslog_facility BETWEEN 0 AND 23),
    cisco_facility       TEXT,
    cisco_subfacility    TEXT,
    facility             TEXT, -- compatibility projection for older clients
    severity             INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 7),
    mnemonic             TEXT,
    message              TEXT NOT NULL,
    raw_message          TEXT,
    protocol             TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    parse_status         TEXT NOT NULL DEFAULT 'parsed'
                         CHECK (parse_status IN ('parsed', 'partial', 'raw'))
);

CREATE INDEX idx_t12_syslog_host_time
    ON t12_syslog_messages(device_host, received_at DESC);
CREATE INDEX idx_t12_syslog_severity_time
    ON t12_syslog_messages(severity, received_at DESC);
CREATE INDEX idx_t12_syslog_source_ip
    ON t12_syslog_messages(source_ip);
CREATE INDEX idx_t12_syslog_cisco_facility_time
    ON t12_syslog_messages(cisco_facility, received_at DESC);
