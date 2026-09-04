-- ============================================================
-- 8. DỮ LIỆU THU THẬP TỪ THIẾT BỊ
--    INFO / COLLECTED DATA
-- ============================================================
-- Các bảng trong nhóm t08_info_* là dữ liệu READ-ONLY
-- từ góc độ cấu hình.
--
-- Chỉ collector được phép:
--   - INSERT dữ liệu thu thập từ thiết bị
--   - UPDATE dữ liệu trạng thái
--   - DELETE snapshot cũ
--
-- Không sử dụng các cột:
--   - sync_status
--   - action_Cfg
--
-- Vì đây không phải dữ liệu cấu hình cần push.
-- ============================================================


-- ============================================================
-- 8a. ROUTING TABLE
-- Nguồn dữ liệu:
--   show ip route
-- ============================================================

CREATE TABLE IF NOT EXISTS t08_info_routing_table (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,

    host                    TEXT    NOT NULL,

    -- Mã giao thức xuất hiện trong output Cisco:
    -- C, L, S, O, O IA, D, D EX, B, R...
    protocol_code           TEXT    NOT NULL,

    -- Tên giao thức đã chuẩn hóa:
    -- connected, local, static, ospf, eigrp, bgp, rip...
    protocol_name           TEXT,

    -- Địa chỉ mạng đích.
    destination             TEXT    NOT NULL,

    -- Hỗ trợ cả IPv4 và IPv6.
    prefix_length           INTEGER NOT NULL
                                      CHECK(prefix_length BETWEEN 0 AND 128),

    administrative_distance INTEGER,
    metric                  INTEGER,

    -- NULL đối với route connected/local hoặc route không có next-hop.
    next_hop                TEXT,

    -- Ví dụ:
    -- 00:05:12
    -- 2w3d
    -- 01:20:40
    route_age               TEXT,

    exit_interface          TEXT,

    -- Cho biết tuyến đường được chọn là tuyến tốt nhất.
    is_best                 INTEGER NOT NULL DEFAULT 1
                                      CHECK(is_best IN (0,1)),

    -- Thời điểm collector thu thập bản ghi.
    collected_at            TEXT    NOT NULL
                                      DEFAULT (datetime('now')),

    -- Lưu dòng output gốc để debug parser.
    raw_line                TEXT
);

CREATE INDEX IF NOT EXISTS ix_t08_routing_host
    ON t08_info_routing_table(host);

CREATE INDEX IF NOT EXISTS ix_t08_routing_destination
    ON t08_info_routing_table(destination, prefix_length);

CREATE INDEX IF NOT EXISTS ix_t08_routing_protocol
    ON t08_info_routing_table(host, protocol_name);

CREATE INDEX IF NOT EXISTS ix_t08_routing_collected_at
    ON t08_info_routing_table(collected_at);

