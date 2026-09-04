-- 10. SYSLOG DESTINATIONS MANAGED PER DEVICE
-- ============================================================
-- Desired configuration and push state belong to device_network.db.
-- Received Syslog messages remain in info_collected.db.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS t10_syslog_servers (
    device_host       TEXT NOT NULL,
    server_ip         TEXT NOT NULL,
    protocol          TEXT NOT NULL CHECK (protocol IN ('udp', 'tcp')),
    port              INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    source_interface  TEXT,
    trap_severity     INTEGER NOT NULL DEFAULT 5
                      CHECK (trap_severity BETWEEN 0 AND 7),
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

-- Marker nội bộ để migration từ bảng legacy chỉ chạy đúng một lần, tránh làm
-- sống lại cấu hình mà người dùng đã xóa khỏi device_network.db.
CREATE TABLE IF NOT EXISTS t10_syslog_migrations (
    migration_key  TEXT PRIMARY KEY,
    completed_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
