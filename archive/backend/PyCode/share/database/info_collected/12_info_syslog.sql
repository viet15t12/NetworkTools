-- Syslog data is isolated in info_collected.db; device data remains read-only.
PRAGMA journal_mode = WAL;

CREATE TABLE t12_syslog_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_host     TEXT NOT NULL,
    source_ip       TEXT NOT NULL,
    device_time     TEXT,
    received_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    facility        TEXT,
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 7),
    mnemonic        TEXT,
    message         TEXT NOT NULL,
    raw_message     TEXT,
    protocol        TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    parse_status    TEXT NOT NULL DEFAULT 'parsed'
                    CHECK (parse_status IN ('parsed', 'partial', 'raw'))
);

CREATE INDEX idx_t12_syslog_host_time
    ON t12_syslog_messages(device_host, received_at DESC);
CREATE INDEX idx_t12_syslog_severity_time
    ON t12_syslog_messages(severity, received_at DESC);
CREATE INDEX idx_t12_syslog_source_ip
    ON t12_syslog_messages(source_ip);
CREATE INDEX idx_t12_syslog_facility_time
    ON t12_syslog_messages(facility, received_at DESC);

CREATE TABLE t12_syslog_device_state (
    device_host       TEXT NOT NULL,
    server_ip         TEXT NOT NULL,
    protocol          TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    port              INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    source_interface  TEXT,
    configured        INTEGER NOT NULL DEFAULT 0 CHECK (configured IN (0, 1)),
    last_result       TEXT,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (device_host, server_ip, protocol, port)
);
