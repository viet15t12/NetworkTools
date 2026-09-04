-- ============================================================
-- 10. DỮ LIỆU ACL THU THẬP TỪ THIẾT BỊ
--     ACL INFO / COLLECTED DATA
-- ============================================================
-- Nguồn dữ liệu tham khảo:
--   show access-lists
--   show ip access-lists
--   show ipv6 access-list
--   show mac access-list
--   show ip interface
--   show running-config | section access-list
--
-- Các bảng t10_info_* là dữ liệu READ-ONLY từ góc độ cấu hình.
--
-- Chỉ collector được phép:
--   - INSERT dữ liệu lấy từ thiết bị
--   - UPDATE trạng thái hoặc thông tin parser
--   - DELETE snapshot cũ
--
-- Không sử dụng:
--   - sync_status
--   - action_Cfg
--
-- Vì đây là dữ liệu được đọc từ thiết bị, không phải dữ liệu
-- cấu hình chờ push.
-- ============================================================


-- ============================================================
-- 10a. ACL DATABASE
-- Lưu thông tin tổng quát của từng ACL được phát hiện trên thiết bị.
-- ============================================================

CREATE TABLE IF NOT EXISTS t10_info_acl_db (
    info_acl_id     INTEGER PRIMARY KEY AUTOINCREMENT,

    host            TEXT    NOT NULL,

    -- Tên hoặc số ACL.
    -- Ví dụ:
    --   10
    --   101
    --   BLOCK_WEB
    --   IPV6_FILTER
    acl_name        TEXT    NOT NULL,

    -- Loại ACL đã chuẩn hóa.
    acl_type        TEXT    NOT NULL
                            CHECK(
                                acl_type IN (
                                    'standard',
                                    'extended',
                                    'dynamic',
                                    'reflexive',
                                    'mac',
                                    'ipv6',
                                    'unknown'
                                )
                            ),

    -- Họ địa chỉ áp dụng cho ACL.
    address_family  TEXT    NOT NULL DEFAULT 'ipv4'
                            CHECK(
                                address_family IN (
                                    'ipv4',
                                    'ipv6',
                                    'mac',
                                    'unknown'
                                )
                            ),

    -- ACL dạng số hoặc dạng tên.
    acl_format      TEXT    DEFAULT 'named'
                            CHECK(
                                acl_format IN (
                                    'numbered',
                                    'named',
                                    'unknown'
                                )
                            ),

    description     TEXT,

    -- Tổng số rule collector phân tích được.
    rule_count      INTEGER NOT NULL DEFAULT 0
                            CHECK(rule_count >= 0),

    -- Cho biết ACL đang được gắn vào interface hay chưa.
    is_applied      INTEGER NOT NULL DEFAULT 0
                            CHECK(is_applied IN (0,1)),

    -- Thời điểm collector thu thập dữ liệu.
    collected_at    TEXT    NOT NULL
                            DEFAULT (datetime('now')),

    -- Phần output gốc tương ứng ACL để debug parser.
    raw_output      TEXT,

    UNIQUE(host, acl_name, address_family)
);


CREATE INDEX IF NOT EXISTS ix_t10_acl_host
    ON t10_info_acl_db(host);

CREATE INDEX IF NOT EXISTS ix_t10_acl_host_name
    ON t10_info_acl_db(host, acl_name);

CREATE INDEX IF NOT EXISTS ix_t10_acl_type
    ON t10_info_acl_db(host, acl_type);

CREATE INDEX IF NOT EXISTS ix_t10_acl_collected_at
    ON t10_info_acl_db(collected_at);


-- ============================================================
-- 10b. ACL RULES
-- Lưu các ACE - Access Control Entry của ACL.
--
-- Bảng này dùng chung cho:
--   - Standard ACL
--   - Extended ACL
--   - Dynamic ACL
--   - Reflexive ACL
--   - IPv6 ACL
--   - MAC ACL
-- ============================================================

CREATE TABLE IF NOT EXISTS t10_info_acl_rules (
    info_rule_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    info_acl_id       INTEGER NOT NULL,

    -- Số thứ tự ACE nếu output thiết bị có sequence.
    sequence          INTEGER CHECK(sequence IS NULL OR sequence >= 0),

    action            TEXT    NOT NULL
                              CHECK(action IN ('permit','deny','remark')),

    -- Giao thức:
    -- ip, tcp, udp, icmp, icmpv6, gre, ospf, esp, ahp...
    -- NULL đối với standard ACL hoặc remark.
    protocol          TEXT,

    -- Biểu diễn nguồn đã chuẩn hóa.
    -- Ví dụ:
    -- any
    -- host 192.168.1.10
    -- 192.168.1.0
    source            TEXT,

    src_wildcard      TEXT,
    src_prefix_length INTEGER
                              CHECK(
                                  src_prefix_length IS NULL
                                  OR src_prefix_length BETWEEN 0 AND 128
                              ),

    -- Toán tử cổng:
    -- eq, neq, lt, gt, range.
    src_port_operator TEXT
                              CHECK(
                                  src_port_operator IS NULL
                                  OR src_port_operator IN (
                                      'eq',
                                      'neq',
                                      'lt',
                                      'gt',
                                      'range'
                                  )
                              ),

    src_port_start    TEXT,
    src_port_end      TEXT,

    -- Đích có thể NULL đối với standard ACL hoặc remark.
    destination       TEXT,

    dst_wildcard      TEXT,
    dst_prefix_length INTEGER
                              CHECK(
                                  dst_prefix_length IS NULL
                                  OR dst_prefix_length BETWEEN 0 AND 128
                              ),

    dst_port_operator TEXT
                              CHECK(
                                  dst_port_operator IS NULL
                                  OR dst_port_operator IN (
                                      'eq',
                                      'neq',
                                      'lt',
                                      'gt',
                                      'range'
                                  )
                              ),

    dst_port_start    TEXT,
    dst_port_end      TEXT,

    -- Các tùy chọn TCP:
    -- established, syn, ack, rst, fin, psh, urg...
    tcp_flags         TEXT,

    -- Loại ICMP:
    -- echo, echo-reply, unreachable...
    icmp_type         TEXT,
    icmp_code         TEXT,

    -- Tên dynamic ACL.
    dynamic_name      TEXT,

    -- Tên reflexive ACL.
    reflect_name      TEXT,

    -- Dùng cho evaluate <reflect-name>.
    evaluate_name     TEXT,

    -- Timeout được thiết bị hiển thị, nếu có.
    timeout_seconds   INTEGER
                              CHECK(
                                  timeout_seconds IS NULL
                                  OR timeout_seconds > 0
                              ),

    -- Nội dung remark.
    remark_text       TEXT,

    -- Tùy chọn log hoặc log-input.
    logging           TEXT
                              CHECK(
                                  logging IS NULL
                                  OR logging IN (
                                      'log',
                                      'log-input'
                                  )
                              ),

    -- Số packet match ACE, lấy từ dạng:
    -- (123 matches)
    match_count       INTEGER DEFAULT 0
                              CHECK(match_count >= 0),

    -- Thông tin hardware match nếu thiết bị hỗ trợ.
    hardware_count    INTEGER
                              CHECK(
                                  hardware_count IS NULL
                                  OR hardware_count >= 0
                              ),

    -- Cho biết rule là rule tạm thời được sinh bởi dynamic
    -- hoặc reflexive ACL.
    is_temporary      INTEGER NOT NULL DEFAULT 0
                              CHECK(is_temporary IN (0,1)),

    -- Cho biết rule được parser nhận diện đầy đủ.
    parsed_ok         INTEGER NOT NULL DEFAULT 1
                              CHECK(parsed_ok IN (0,1)),

    collected_at      TEXT    NOT NULL
                              DEFAULT (datetime('now')),

    -- Dòng output nguyên bản của ACE.
    raw_line          TEXT,

    FOREIGN KEY (info_acl_id)
        REFERENCES t10_info_acl_db(info_acl_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS ix_t10_acl_rules_acl
    ON t10_info_acl_rules(info_acl_id);

CREATE INDEX IF NOT EXISTS ix_t10_acl_rules_sequence
    ON t10_info_acl_rules(info_acl_id, sequence);

CREATE INDEX IF NOT EXISTS ix_t10_acl_rules_action
    ON t10_info_acl_rules(action);

CREATE INDEX IF NOT EXISTS ix_t10_acl_rules_protocol
    ON t10_info_acl_rules(protocol);

CREATE INDEX IF NOT EXISTS ix_t10_acl_rules_collected_at
    ON t10_info_acl_rules(collected_at);


-- ============================================================
-- 10c. MAC ACL RULE DETAILS
-- Lưu phần dữ liệu riêng của MAC ACL.
--
-- Một bản ghi trong bảng này mở rộng một rule tương ứng trong
-- t10_info_acl_rules.
-- ============================================================

CREATE TABLE IF NOT EXISTS t10_info_mac_acl_rule_details (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    info_rule_id    INTEGER NOT NULL UNIQUE,

    src_mac         TEXT,
    src_mask        TEXT,

    dst_mac         TEXT,
    dst_mask        TEXT,

    -- Ví dụ:
    -- ipv4
    -- ipv6
    -- arp
    -- 0x0800
    ethertype       TEXT,

    -- Có thể chứa vlan, cos hoặc các tùy chọn MAC ACL khác.
    vlan_id         INTEGER
                            CHECK(
                                vlan_id IS NULL
                                OR vlan_id BETWEEN 1 AND 4094
                            ),

    cos_value       INTEGER
                            CHECK(
                                cos_value IS NULL
                                OR cos_value BETWEEN 0 AND 7
                            ),

    raw_line        TEXT,

    FOREIGN KEY (info_rule_id)
        REFERENCES t10_info_acl_rules(info_rule_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS ix_t10_mac_acl_src
    ON t10_info_mac_acl_rule_details(src_mac);

CREATE INDEX IF NOT EXISTS ix_t10_mac_acl_dst
    ON t10_info_mac_acl_rule_details(dst_mac);


-- ============================================================
-- 10d. ACL ĐƯỢC ÁP DỤNG TRÊN INTERFACE
-- Nguồn dữ liệu:
--   show ip interface
--   show ipv6 interface
--   show running-config interface <interface>
-- ============================================================

CREATE TABLE IF NOT EXISTS t10_info_iface_acl (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,

    host             TEXT    NOT NULL,

    -- Có thể liên kết được với t02_interface_name hoặc để NULL
    -- khi collector chưa tìm thấy iface_id tương ứng.
    iface_id         INTEGER,

    -- Tên interface lấy trực tiếp từ thiết bị.
    interface_name   TEXT    NOT NULL,

    info_acl_id      INTEGER,

    -- Tên ACL lấy trực tiếp từ output.
    -- Vẫn lưu acl_name để tránh mất thông tin nếu chưa liên kết
    -- được với t10_info_acl_db.
    acl_name         TEXT    NOT NULL,

    direction        TEXT    NOT NULL
                             CHECK(direction IN ('in','out')),

    address_family   TEXT    NOT NULL DEFAULT 'ipv4'
                             CHECK(
                                 address_family IN (
                                     'ipv4',
                                     'ipv6',
                                     'mac',
                                     'unknown'
                                 )
                             ),

    -- Loại cách áp ACL.
    -- interface: ip access-group / ipv6 traffic-filter
    -- vlan: VLAN access-map
    -- control-plane: control-plane ACL
    apply_scope      TEXT    NOT NULL DEFAULT 'interface'
                             CHECK(
                                 apply_scope IN (
                                     'interface',
                                     'vlan',
                                     'control-plane',
                                     'line',
                                     'unknown'
                                 )
                             ),

    collected_at     TEXT    NOT NULL
                             DEFAULT (datetime('now')),

    raw_line         TEXT,

    UNIQUE(
        host,
        interface_name,
        acl_name,
        direction,
        address_family,
        apply_scope
    ),


    FOREIGN KEY (info_acl_id)
        REFERENCES t10_info_acl_db(info_acl_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS ix_t10_iface_acl_host
    ON t10_info_iface_acl(host);

CREATE INDEX IF NOT EXISTS ix_t10_iface_acl_interface
    ON t10_info_iface_acl(host, interface_name);

CREATE INDEX IF NOT EXISTS ix_t10_iface_acl_acl
    ON t10_info_iface_acl(info_acl_id);

CREATE INDEX IF NOT EXISTS ix_t10_iface_acl_name
    ON t10_info_iface_acl(host, acl_name);

CREATE INDEX IF NOT EXISTS ix_t10_iface_acl_collected_at
    ON t10_info_iface_acl(collected_at);


-- ============================================================
-- 10e. ACL COLLECTION SNAPSHOT
-- Quản lý từng lần chạy collector ACL.
--
-- Bảng này giúp phân biệt dữ liệu của nhiều lần thu thập và
-- theo dõi lỗi lệnh hoặc lỗi parser.
-- ============================================================

CREATE TABLE IF NOT EXISTS t10_info_acl_collection (
    collection_id    INTEGER PRIMARY KEY AUTOINCREMENT,

    host             TEXT    NOT NULL,

    command          TEXT    NOT NULL,

    started_at       TEXT    NOT NULL
                             DEFAULT (datetime('now')),

    completed_at     TEXT,

    collection_state TEXT    NOT NULL DEFAULT 'running'
                             CHECK(
                                 collection_state IN (
                                     'running',
                                     'completed',
                                     'partial',
                                     'failed'
                                 )
                             ),

    acl_count        INTEGER NOT NULL DEFAULT 0
                             CHECK(acl_count >= 0),

    rule_count       INTEGER NOT NULL DEFAULT 0
                             CHECK(rule_count >= 0),

    error_message    TEXT,

    raw_output       TEXT
);


CREATE INDEX IF NOT EXISTS ix_t10_acl_collection_host
    ON t10_info_acl_collection(host);

CREATE INDEX IF NOT EXISTS ix_t10_acl_collection_started
    ON t10_info_acl_collection(started_at);

CREATE INDEX IF NOT EXISTS ix_t10_acl_collection_state
    ON t10_info_acl_collection(host, collection_state);
