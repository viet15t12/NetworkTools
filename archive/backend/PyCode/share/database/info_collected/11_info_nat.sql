-- ============================================================
-- 11. DỮ LIỆU NAT THU THẬP TỪ THIẾT BỊ
--     NAT INFO / COLLECTED DATA
-- ============================================================
-- Nguồn dữ liệu:
--   show running-config | include ip nat
--   show running-config | section ip nat
--   show ip nat translations
--   show ip nat translations verbose
--   show ip nat statistics
--
-- Không sử dụng:
--   show ip interface
--
-- Vì trạng thái:
--   ip nat inside
--   ip nat outside
--
-- là thuộc tính của interface và phải được collector interface
-- xử lý trong nhóm dữ liệu thông tin interface.
--
-- Các bảng t11_info_nat_* là dữ liệu READ-ONLY từ góc độ
-- cấu hình.
--
-- Không sử dụng:
--   - success
--   - action_Cfg
--
-- Vì đây là dữ liệu được thu thập từ thiết bị, không phải dữ
-- liệu cấu hình chờ push.
-- ============================================================

-- ============================================================
-- 11a. NAT DATABASE / NAT CONFIGURATION SUMMARY
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_db (
    info_nat_id         INTEGER PRIMARY KEY AUTOINCREMENT,

    host                TEXT    NOT NULL,

    -- Tên logic do collector sinh ra.
    nat_name            TEXT    NOT NULL,

    nat_type            TEXT    NOT NULL
                                CHECK(
                                    nat_type IN (
                                        'static',
                                        'dynamic',
                                        'overload',
                                        'port_forward',
                                        'exempt',
                                        'unknown'
                                    )
                                ),

    description         TEXT,

    parsed_ok           INTEGER NOT NULL DEFAULT 1
                                CHECK(parsed_ok IN (0,1)),

    collected_at        TEXT    NOT NULL
                                DEFAULT (datetime('now')),

    raw_line            TEXT,

    UNIQUE(host, nat_name)
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_db_host
    ON t11_info_nat_db(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_db_type
    ON t11_info_nat_db(host, nat_type);

CREATE INDEX IF NOT EXISTS ix_t11_nat_db_collected_at
    ON t11_info_nat_db(collected_at);


-- ============================================================
-- 11b. NAT POOLS
-- Nguồn:
--   ip nat pool <name> <start-ip> <end-ip> netmask <mask>
--   ip nat pool <name> <start-ip> <end-ip> prefix-length <n>
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_pools (
    info_pool_id        INTEGER PRIMARY KEY AUTOINCREMENT,

    host                TEXT    NOT NULL,

    pool_name           TEXT    NOT NULL,

    start_ip            TEXT    NOT NULL,
    end_ip              TEXT    NOT NULL,

    netmask             TEXT,
    prefix_length       INTEGER CHECK(prefix_length IS NULL OR prefix_length BETWEEN 0 AND 32),

    address_count       INTEGER
                                CHECK(
                                    address_count IS NULL
                                    OR address_count >= 0
                                ),

    allocated_count     INTEGER
                                CHECK(
                                    allocated_count IS NULL
                                    OR allocated_count >= 0
                                ),

    collected_at        TEXT    NOT NULL
                                DEFAULT (datetime('now')),

    raw_line            TEXT,

    CHECK(netmask IS NOT NULL OR prefix_length IS NOT NULL),
    UNIQUE(host, pool_name)
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_pool_host
    ON t11_info_nat_pools(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_pool_name
    ON t11_info_nat_pools(host, pool_name);

CREATE INDEX IF NOT EXISTS ix_t11_nat_pool_collected_at
    ON t11_info_nat_pools(collected_at);


-- ============================================================
-- 11c. STATIC NAT / STATIC PAT MAPPINGS
-- Nguồn:
--   ip nat inside source static <local> <global>
--   ip nat inside source static tcp ...
--   ip nat inside source static udp ...
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_static_mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    host                TEXT    NOT NULL,

    info_nat_id         INTEGER,

    inside_local_ip     TEXT    NOT NULL,
    inside_global_ip    TEXT    NOT NULL,

    protocol            TEXT
                                CHECK(
                                    protocol IS NULL
                                    OR lower(protocol) IN (
                                        'tcp',
                                        'udp',
                                        'icmp'
                                    )
                                ),

    local_port          INTEGER CHECK(local_port IS NULL OR local_port BETWEEN 1 AND 65535),
    global_port         INTEGER CHECK(global_port IS NULL OR global_port BETWEEN 1 AND 65535),

    is_extendable       INTEGER NOT NULL DEFAULT 0
                                CHECK(is_extendable IN (0,1)),

    no_alias            INTEGER NOT NULL DEFAULT 0
                                CHECK(no_alias IN (0,1)),

    route_map_name      TEXT,
    redundancy_name     TEXT,
    description         TEXT,

    collected_at        TEXT    NOT NULL
                                DEFAULT (datetime('now')),

    raw_line            TEXT,

    CHECK((local_port IS NULL AND global_port IS NULL) OR
          (local_port IS NOT NULL AND global_port IS NOT NULL)),
    UNIQUE(
        host,
        inside_local_ip,
        inside_global_ip,
        protocol,
        local_port,
        global_port
    ),

    FOREIGN KEY (info_nat_id)
        REFERENCES t11_info_nat_db(info_nat_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_static_host
    ON t11_info_nat_static_mappings(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_static_local
    ON t11_info_nat_static_mappings(host, inside_local_ip);

CREATE INDEX IF NOT EXISTS ix_t11_nat_static_global
    ON t11_info_nat_static_mappings(host, inside_global_ip);

CREATE INDEX IF NOT EXISTS ix_t11_nat_static_collected_at
    ON t11_info_nat_static_mappings(collected_at);


-- ============================================================
-- 11d. DYNAMIC NAT / PAT RULES
-- Nguồn:
--   ip nat inside source list <acl> pool <pool>
--   ip nat inside source list <acl> pool <pool> overload
--   ip nat inside source list <acl> interface <iface> overload
--   ip nat inside source route-map <name> pool <pool>
--   ip nat inside source route-map <name> interface <iface>
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_dynamic_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    host                TEXT    NOT NULL,

    info_nat_id         INTEGER,

    match_type          TEXT    NOT NULL
                                CHECK(
                                    match_type IN (
                                        'acl',
                                        'route-map',
                                        'unknown'
                                    )
                                ),

    acl_name            TEXT,
    route_map_name      TEXT,

    translation_type    TEXT    NOT NULL
                                CHECK(
                                    translation_type IN (
                                        'pool',
                                        'interface',
                                        'unknown'
                                    )
                                ),

    pool_name           TEXT,

    -- Đây là interface được tham chiếu trong câu lệnh NAT:
    -- ip nat inside source list ... interface ...
    --
    -- Không phải thuộc tính ip nat inside/outside của interface.
    outside_interface   TEXT,

    overload            INTEGER NOT NULL DEFAULT 0
                                CHECK(overload IN (0,1)),

    description         TEXT,

    collected_at        TEXT    NOT NULL
                                DEFAULT (datetime('now')),

    raw_line            TEXT,

    CHECK((match_type = 'acl' AND acl_name IS NOT NULL) OR
          (match_type = 'route-map' AND route_map_name IS NOT NULL) OR
          match_type = 'unknown'),
    CHECK((translation_type = 'pool' AND pool_name IS NOT NULL) OR
          (translation_type = 'interface' AND outside_interface IS NOT NULL) OR
          translation_type = 'unknown'),
    UNIQUE(
        host,
        match_type,
        acl_name,
        route_map_name,
        translation_type,
        pool_name,
        outside_interface
    ),

    FOREIGN KEY (info_nat_id)
        REFERENCES t11_info_nat_db(info_nat_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_host
    ON t11_info_nat_dynamic_rules(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_acl
    ON t11_info_nat_dynamic_rules(host, acl_name);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_route_map
    ON t11_info_nat_dynamic_rules(host, route_map_name);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_pool
    ON t11_info_nat_dynamic_rules(host, pool_name);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_interface
    ON t11_info_nat_dynamic_rules(host, outside_interface);

CREATE INDEX IF NOT EXISTS ix_t11_nat_dynamic_collected_at
    ON t11_info_nat_dynamic_rules(collected_at);


-- ============================================================
-- 11e. ACTIVE NAT TRANSLATIONS
-- Nguồn:
--   show ip nat translations
--   show ip nat translations verbose
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_translations (
    translation_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    host                TEXT    NOT NULL,

    protocol            TEXT,

    inside_global_ip    TEXT,
    inside_global_port  INTEGER CHECK(inside_global_port IS NULL OR inside_global_port BETWEEN 1 AND 65535),

    inside_local_ip     TEXT,
    inside_local_port   INTEGER CHECK(inside_local_port IS NULL OR inside_local_port BETWEEN 1 AND 65535),

    outside_local_ip    TEXT,
    outside_local_port  INTEGER CHECK(outside_local_port IS NULL OR outside_local_port BETWEEN 1 AND 65535),

    outside_global_ip   TEXT,
    outside_global_port INTEGER CHECK(outside_global_port IS NULL OR outside_global_port BETWEEN 1 AND 65535),

    translation_type    TEXT
                                CHECK(
                                    translation_type IS NULL
                                    OR translation_type IN (
                                        'static',
                                        'dynamic',
                                        'extended',
                                        'unknown'
                                    )
                                ),

    expires_in_seconds  INTEGER
                                CHECK(
                                    expires_in_seconds IS NULL
                                    OR expires_in_seconds >= 0
                                ),

    use_count           INTEGER
                                CHECK(
                                    use_count IS NULL
                                    OR use_count >= 0
                                ),

    flags               TEXT,

    collected_at        TEXT    NOT NULL
                                DEFAULT (datetime('now')),

    raw_line            TEXT
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_host
    ON t11_info_nat_translations(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_inside_local
    ON t11_info_nat_translations(host, inside_local_ip);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_inside_global
    ON t11_info_nat_translations(host, inside_global_ip);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_outside_global
    ON t11_info_nat_translations(host, outside_global_ip);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_protocol
    ON t11_info_nat_translations(host, protocol);

CREATE INDEX IF NOT EXISTS ix_t11_nat_translation_collected_at
    ON t11_info_nat_translations(collected_at);


-- ============================================================
-- 11f. NAT STATISTICS
-- Nguồn:
--   show ip nat statistics
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_statistics (
    statistics_id          INTEGER PRIMARY KEY AUTOINCREMENT,

    host                   TEXT    NOT NULL,

    total_active           INTEGER NOT NULL DEFAULT 0
                                   CHECK(total_active >= 0),

    static_active          INTEGER NOT NULL DEFAULT 0
                                   CHECK(static_active >= 0),

    dynamic_active         INTEGER NOT NULL DEFAULT 0
                                   CHECK(dynamic_active >= 0),

    extended_active        INTEGER NOT NULL DEFAULT 0
                                   CHECK(extended_active >= 0),

    peak_translations      INTEGER
                                   CHECK(
                                       peak_translations IS NULL
                                       OR peak_translations >= 0
                                   ),

    hits                   INTEGER
                                   CHECK(hits IS NULL OR hits >= 0),

    misses                 INTEGER
                                   CHECK(misses IS NULL OR misses >= 0),

    expired_translations   INTEGER
                                   CHECK(
                                       expired_translations IS NULL
                                       OR expired_translations >= 0
                                   ),

    dynamic_mappings_count INTEGER
                                   CHECK(
                                       dynamic_mappings_count IS NULL
                                       OR dynamic_mappings_count >= 0
                                   ),

    collected_at           TEXT    NOT NULL
                                   DEFAULT (datetime('now')),

    raw_output             TEXT
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_statistics_host
    ON t11_info_nat_statistics(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_statistics_collected_at
    ON t11_info_nat_statistics(collected_at);


-- ============================================================
-- 11g. NAT COLLECTION HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS t11_info_nat_collection (
    collection_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    host               TEXT    NOT NULL,

    command            TEXT    NOT NULL,

    started_at         TEXT    NOT NULL
                               DEFAULT (datetime('now')),

    completed_at       TEXT,

    collection_state   TEXT    NOT NULL DEFAULT 'running'
                               CHECK(
                                   collection_state IN (
                                       'running',
                                       'completed',
                                       'partial',
                                       'failed'
                                   )
                               ),

    static_count       INTEGER NOT NULL DEFAULT 0
                               CHECK(static_count >= 0),

    dynamic_count      INTEGER NOT NULL DEFAULT 0
                               CHECK(dynamic_count >= 0),

    translation_count  INTEGER NOT NULL DEFAULT 0
                               CHECK(translation_count >= 0),

    pool_count         INTEGER NOT NULL DEFAULT 0
                               CHECK(pool_count >= 0),

    error_message      TEXT,
    raw_output         TEXT
);

CREATE INDEX IF NOT EXISTS ix_t11_nat_collection_host
    ON t11_info_nat_collection(host);

CREATE INDEX IF NOT EXISTS ix_t11_nat_collection_state
    ON t11_info_nat_collection(host, collection_state);

CREATE INDEX IF NOT EXISTS ix_t11_nat_collection_started_at
    ON t11_info_nat_collection(started_at);
