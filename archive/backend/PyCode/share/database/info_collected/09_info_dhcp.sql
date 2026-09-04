-- ============================================================
-- 9. THÔNG TIN DHCP THU THẬP TỪ THIẾT BỊ
--    DHCP INFO / COLLECTED DATA
-- ============================================================
-- Các bảng này chỉ được ghi bởi collector.
-- Không chứa success hoặc action_Cfg.
-- ============================================================


-- ============================================================
-- 9a. DHCP POOL STATUS
-- Nguồn dữ liệu:
--   show ip dhcp pool
-- ============================================================

CREATE TABLE IF NOT EXISTS t09_info_dhcp_pool (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    host                  TEXT    NOT NULL,

    -- Tên DHCP pool trên thiết bị.
    pool_name             TEXT    NOT NULL,

    -- Network được cấu hình trong pool.
    network               TEXT,

    subnet_mask           TEXT,

    prefix_length         INTEGER
                                  CHECK(
                                      prefix_length IS NULL
                                      OR prefix_length BETWEEN 0 AND 128
                                  ),

    -- Phạm vi IP thực tế của pool.
    first_address         TEXT,
    last_address          TEXT,

    -- Current index trong output show ip dhcp pool.
    current_index         TEXT,

    total_addresses       INTEGER NOT NULL DEFAULT 0
                                  CHECK(total_addresses >= 0),

    leased_addresses      INTEGER NOT NULL DEFAULT 0
                                  CHECK(leased_addresses >= 0),

    excluded_addresses    INTEGER NOT NULL DEFAULT 0
                                  CHECK(excluded_addresses >= 0),

    available_addresses   INTEGER NOT NULL DEFAULT 0
                                  CHECK(available_addresses >= 0),

    utilization_percent   REAL
                                  CHECK(
                                      utilization_percent IS NULL
                                      OR utilization_percent BETWEEN 0 AND 100
                                  ),

    -- Utilization mark high/low của Cisco DHCP pool.
    high_utilization      INTEGER
                                  CHECK(
                                      high_utilization IS NULL
                                      OR high_utilization BETWEEN 0 AND 100
                                  ),

    low_utilization       INTEGER
                                  CHECK(
                                      low_utilization IS NULL
                                      OR low_utilization BETWEEN 0 AND 100
                                  ),

    pending_event         TEXT,

    collected_at          TEXT    NOT NULL
                                  DEFAULT (datetime('now')),

    -- Lưu nguyên output của pool tương ứng nếu cần debug.
    raw_output            TEXT
);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_pool_host
    ON t09_info_dhcp_pool(host);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_pool_host_name
    ON t09_info_dhcp_pool(host, pool_name);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_pool_network
    ON t09_info_dhcp_pool(network, prefix_length);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_pool_collected_at
    ON t09_info_dhcp_pool(collected_at);


-- ============================================================
-- 9b. DHCP BINDING / LEASE
-- Nguồn dữ liệu:
--   show ip dhcp binding
-- ============================================================

CREATE TABLE IF NOT EXISTS t09_info_dhcp_binding (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    host                  TEXT    NOT NULL,

    -- Có thể NULL nếu output không xác định trực tiếp pool.
    pool_name             TEXT,

    -- Địa chỉ IP đang được cấp.
    ip_address            TEXT    NOT NULL,

    -- Client identifier của DHCP client.
    client_id             TEXT,

    -- MAC address đã chuẩn hóa nếu parser lấy được.
    hardware_address      TEXT,

    username              TEXT,

    -- Chuỗi thời gian hết hạn theo output thiết bị.
    lease_expiration      TEXT,

    -- Automatic, Manual, Infinite...
    lease_type            TEXT,

    -- Active, Expired, Selecting...
    binding_state         TEXT,

    -- Interface liên quan nếu thiết bị cung cấp.
    interface_name        TEXT,

    collected_at          TEXT    NOT NULL
                                  DEFAULT (datetime('now')),

    -- Dòng output gốc.
    raw_line              TEXT
);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_host
    ON t09_info_dhcp_binding(host);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_ip
    ON t09_info_dhcp_binding(host, ip_address);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_client
    ON t09_info_dhcp_binding(host, client_id);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_mac
    ON t09_info_dhcp_binding(host, hardware_address);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_pool
    ON t09_info_dhcp_binding(host, pool_name);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_binding_collected_at
    ON t09_info_dhcp_binding(collected_at);


-- ============================================================
-- 9c. DHCP CONFLICT
-- Nguồn dữ liệu:
--   show ip dhcp conflict
-- ============================================================

CREATE TABLE IF NOT EXISTS t09_info_dhcp_conflict (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    host                  TEXT    NOT NULL,

    -- Địa chỉ IP bị phát hiện trùng.
    ip_address            TEXT    NOT NULL,

    -- Ví dụ:
    -- Ping
    -- Gratuitous ARP
    detection_method      TEXT,

    -- Thời điểm phát hiện theo output thiết bị.
    detection_time        TEXT,

    collected_at          TEXT    NOT NULL
                                  DEFAULT (datetime('now')),

    raw_line              TEXT
);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_conflict_host
    ON t09_info_dhcp_conflict(host);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_conflict_ip
    ON t09_info_dhcp_conflict(host, ip_address);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_conflict_collected_at
    ON t09_info_dhcp_conflict(collected_at);


-- ============================================================
-- 9d. DHCP SERVER STATISTICS
-- Nguồn dữ liệu:
--   show ip dhcp server statistics
--
-- Bảng này có thể lưu lịch sử để:
--   - vẽ biểu đồ
--   - theo dõi số gói DHCP
--   - phát hiện DHCP NAK tăng bất thường
-- ============================================================

CREATE TABLE IF NOT EXISTS t09_info_dhcp_server_statistics (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,

    host                    TEXT    NOT NULL,

    memory_usage            INTEGER
                                    CHECK(
                                        memory_usage IS NULL
                                        OR memory_usage >= 0
                                    ),

    address_pools           INTEGER
                                    CHECK(
                                        address_pools IS NULL
                                        OR address_pools >= 0
                                    ),

    database_agents         INTEGER
                                    CHECK(
                                        database_agents IS NULL
                                        OR database_agents >= 0
                                    ),

    automatic_bindings      INTEGER
                                    CHECK(
                                        automatic_bindings IS NULL
                                        OR automatic_bindings >= 0
                                    ),

    manual_bindings         INTEGER
                                    CHECK(
                                        manual_bindings IS NULL
                                        OR manual_bindings >= 0
                                    ),

    expired_bindings        INTEGER
                                    CHECK(
                                        expired_bindings IS NULL
                                        OR expired_bindings >= 0
                                    ),

    malformed_messages      INTEGER
                                    CHECK(
                                        malformed_messages IS NULL
                                        OR malformed_messages >= 0
                                    ),

    dhcp_discover_received  INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_discover_received >= 0),

    dhcp_offer_sent         INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_offer_sent >= 0),

    dhcp_request_received   INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_request_received >= 0),

    dhcp_decline_received   INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_decline_received >= 0),

    dhcp_ack_sent           INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_ack_sent >= 0),

    dhcp_nak_sent           INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_nak_sent >= 0),

    dhcp_release_received   INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_release_received >= 0),

    dhcp_inform_received    INTEGER NOT NULL DEFAULT 0
                                    CHECK(dhcp_inform_received >= 0),

    collected_at            TEXT    NOT NULL
                                    DEFAULT (datetime('now')),

    raw_output              TEXT
);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_statistics_host
    ON t09_info_dhcp_server_statistics(host);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_statistics_collected_at
    ON t09_info_dhcp_server_statistics(collected_at);


-- ============================================================
-- 9e. DHCP DATABASE AGENT
-- Nguồn dữ liệu:
--   show ip dhcp database
--
-- Chỉ có dữ liệu khi thiết bị được cấu hình DHCP database agent.
-- ============================================================

CREATE TABLE IF NOT EXISTS t09_info_dhcp_database (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,

    host                  TEXT    NOT NULL,

    -- Ví dụ:
    -- flash:dhcp.dat
    -- ftp://server/dhcp-db
    -- tftp://server/dhcp-db
    database_url          TEXT,

    write_delay_seconds   INTEGER
                                  CHECK(
                                      write_delay_seconds IS NULL
                                      OR write_delay_seconds >= 0
                                  ),

    timeout_seconds       INTEGER
                                  CHECK(
                                      timeout_seconds IS NULL
                                      OR timeout_seconds >= 0
                                  ),

    last_write_time       TEXT,
    last_read_time        TEXT,

    -- Trạng thái database agent:
    -- OK, Error, Disabled, Pending...
    status                TEXT,

    collected_at          TEXT    NOT NULL
                                  DEFAULT (datetime('now')),

    raw_output            TEXT
);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_database_host
    ON t09_info_dhcp_database(host);

CREATE INDEX IF NOT EXISTS ix_t09_dhcp_database_collected_at
    ON t09_info_dhcp_database(collected_at);
