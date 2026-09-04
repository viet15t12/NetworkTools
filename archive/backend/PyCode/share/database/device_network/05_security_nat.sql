-- 5. BẢO MẬT & NAT (SECURITY, ACL & NAT)
-- ========================================================== 

-- 5a. ACL Database
-- t05_ACL_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description / remark
--   * change acl_name or acl_type by replace (success = -1 + new row success = 0)
--   * change description by keeping row and setting action_Cfg
--   * rule child tables only use success.
CREATE TABLE t05_ACL_DB (
    Acl_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_name     TEXT NOT NULL,           
    acl_type     TEXT NOT NULL,           
    host         TEXT NOT NULL,
    description  TEXT,                    
    success      INTEGER DEFAULT 0,       
    action_Cfg   INTEGER DEFAULT 1,       
    CHECK(success IN (-1,0,1)),
    CHECK(action_Cfg >= 0),
    CHECK(acl_type IN ('standard','extended','dynamic','reflexive','mac')),
    UNIQUE (host, acl_name),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

CREATE TABLE t05_standard_acl_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id      INTEGER NOT NULL,
    sequence    INTEGER,
    action      TEXT NOT NULL CHECK(action IN ('permit','deny')),
    source      TEXT NOT NULL,            
    wildcard    TEXT,                     
    success     INTEGER DEFAULT 0,        
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_extended_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id          INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL CHECK(action IN ('permit','deny')),
    protocol        TEXT NOT NULL,        
    source          TEXT NOT NULL,
    src_wildcard    TEXT,
    src_port        TEXT,
    destination     TEXT NOT NULL,
    dst_wildcard    TEXT,
    dst_port        TEXT,
    success         INTEGER DEFAULT 0,    
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_dynamic_acl_rules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id           INTEGER NOT NULL,
    sequence         INTEGER,
    action           TEXT NOT NULL CHECK(action IN ('permit','deny')),
    protocol         TEXT NOT NULL,
    source           TEXT NOT NULL,
    src_wildcard     TEXT,
    src_port         TEXT,
    destination      TEXT NOT NULL,
    dst_wildcard     TEXT,
    dst_port         TEXT,
    dynamic_name     TEXT NOT NULL,       
    timeout_seconds  INTEGER DEFAULT 300 CHECK(timeout_seconds > 0),
    success          INTEGER DEFAULT 0,   
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_reflexive_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id          INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL CHECK(action IN ('permit','deny')),
    protocol        TEXT NOT NULL,
    source          TEXT NOT NULL,
    src_wildcard    TEXT,
    src_port        TEXT,
    destination     TEXT NOT NULL,
    dst_wildcard    TEXT,
    dst_port        TEXT,
    reflect_name    TEXT,                 
    timeout_seconds INTEGER DEFAULT 300 CHECK(timeout_seconds > 0),
    success         INTEGER DEFAULT 0,    
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_mac_acl_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id      INTEGER NOT NULL,
    sequence    INTEGER,
    action      TEXT NOT NULL CHECK(action IN ('permit','deny')),
    src_mac     TEXT NOT NULL,
    src_mask    TEXT,
    dst_mac     TEXT,
    dst_mask    TEXT,
    ethertype   TEXT,
    success     INTEGER DEFAULT 0,        
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t05_router_iface_acl (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    acl_id          INTEGER NOT NULL,               
    direction       TEXT    NOT NULL CHECK(direction IN ('in','out')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, direction),                    
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (acl_id) REFERENCES t05_ACL_DB(Acl_id) ON DELETE CASCADE
);

-- 5b. Route Map
CREATE TABLE t05_route_map_db (
    route_map_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    route_map_name TEXT NOT NULL,
    host           TEXT NOT NULL,
    description    TEXT,
    success        INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (host, route_map_name),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

-- 5c. NAT ACL
-- t05_NAT_ACL_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description
--   * change acl_name or acl_type by replace (success = -1 + new row success = 0)
--   * change description by setting bit0 in action_Cfg
--   * rule child tables only use success.
CREATE TABLE t05_NAT_ACL_DB (
    nat_acl_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_name        TEXT NOT NULL,
    acl_type        TEXT NOT NULL CHECK(acl_type IN ('standard','extended')),
    host            TEXT NOT NULL,
    description     TEXT,
    success         INTEGER DEFAULT 0,
    action_Cfg      INTEGER DEFAULT 1,
    CHECK(success IN (-1,0,1)),
    CHECK(action_Cfg >= 0),
    UNIQUE (host, acl_name),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

CREATE TABLE t05_route_map_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    route_map_id   INTEGER NOT NULL,
    sequence       INTEGER NOT NULL,
    action         TEXT NOT NULL CHECK(action IN ('permit','deny')),
    nat_acl_id     INTEGER,          
    success        INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(sequence > 0),
    UNIQUE (route_map_id, sequence),
    FOREIGN KEY (route_map_id) REFERENCES t05_route_map_db(route_map_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id)   REFERENCES t05_NAT_ACL_DB(nat_acl_id)
);

CREATE TABLE t05_nat_standard_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_acl_id      INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL CHECK(action IN ('permit','deny')),
    source          TEXT NOT NULL,
    wildcard        TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    UNIQUE (nat_acl_id, sequence),
    FOREIGN KEY (nat_acl_id) REFERENCES t05_NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_nat_extended_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_acl_id      INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL CHECK(action IN ('permit','deny')),
    protocol        TEXT NOT NULL,
    source          TEXT NOT NULL,
    src_wildcard    TEXT,
    src_port        TEXT,
    destination     TEXT NOT NULL,
    dst_wildcard    TEXT,
    dst_port        TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(sequence IS NULL OR sequence > 0),
    UNIQUE (nat_acl_id, sequence),
    FOREIGN KEY (nat_acl_id) REFERENCES t05_NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

-- 5d. NAT Core
-- t05_NAT_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description
--   * change nat_name or nat_type by replace (success = -1 + new row success = 0)
--   * change description by keeping row and setting action_Cfg
--   * NAT child tables only use success.
CREATE TABLE t05_NAT_DB (
    nat_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_name            TEXT NOT NULL,
    nat_type            TEXT NOT NULL CHECK(nat_type IN ('static','dynamic','overload','port_forward')),
    host                TEXT NOT NULL,
    description         TEXT,
    success             INTEGER DEFAULT 0,
    action_Cfg          INTEGER DEFAULT 1,
    CHECK(success IN (-1,0,1)),
    CHECK(action_Cfg >= 0),
    UNIQUE (host, nat_name),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

-- LƯU Ý: "ip nat inside/outside" trên Cisco là thuộc tính TOÀN CỤC của interface,
-- không gắn với 1 nat_id cụ thể. Bảng t05_router_iface_nat (khóa iface_id, không
-- có nat_id) mới phản ánh đúng ngữ nghĩa đó. Bảng t05_nat_interfaces bên dưới lại
-- gắn role theo từng nat_id -- nếu 1 host có nhiều nat_id, 2 bảng có thể ghi nhận
-- role khác nhau cho cùng 1 interface mà DB không phát hiện được. Khuyến nghị:
-- coi t05_router_iface_nat là nguồn dữ liệu chính; nếu vẫn cần t05_nat_interfaces
-- (để biết ACL/pool nào áp cho NAT nào), chỉ dùng nó cho mục đích tra cứu, không
-- ghi role song song ở cả 2 nơi.
CREATE TABLE t05_nat_interfaces (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    t02_interface_name      TEXT NOT NULL,
    nat_role            TEXT NOT NULL CHECK(nat_role IN ('inside','outside')),
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (nat_id, t02_interface_name),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t05_router_iface_nat (
    iface_id        INTEGER PRIMARY KEY,
    nat_role        TEXT    NOT NULL CHECK(nat_role IN ('inside','outside')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE t05_nat_pools (
    pool_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    pool_name           TEXT NOT NULL,
    start_ip            TEXT NOT NULL,
    end_ip              TEXT NOT NULL,
    netmask             TEXT,
    prefix_length       INTEGER,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(netmask IS NOT NULL OR prefix_length IS NOT NULL),
    CHECK(prefix_length IS NULL OR (prefix_length BETWEEN 0 AND 32)),
    UNIQUE (nat_id, pool_name),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE t05_nat_static_mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    inside_local_ip     TEXT NOT NULL,
    inside_global_ip    TEXT NOT NULL,
    protocol            TEXT,
    local_port          INTEGER,
    global_port         INTEGER,
    is_extendable       INTEGER DEFAULT 0,
    description         TEXT,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(is_extendable IN (0,1)),
    CHECK(local_port IS NULL OR (local_port BETWEEN 1 AND 65535)),
    CHECK(global_port IS NULL OR (global_port BETWEEN 1 AND 65535)),
    CHECK((local_port IS NULL AND global_port IS NULL) OR (local_port IS NOT NULL AND global_port IS NOT NULL)),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE t05_nat_dynamic_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    nat_acl_id          INTEGER NOT NULL,
    pool_id             INTEGER NOT NULL,
    overload            INTEGER DEFAULT 0,
    description         TEXT,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(overload IN (0,1)),
    UNIQUE (nat_id, nat_acl_id, pool_id),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id) REFERENCES t05_NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE,
    FOREIGN KEY (pool_id) REFERENCES t05_nat_pools(pool_id) ON DELETE CASCADE
);

CREATE TABLE t05_nat_overload_interface_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    nat_acl_id          INTEGER NOT NULL,
    outside_interface   TEXT NOT NULL,
    overload            INTEGER DEFAULT 1,
    description         TEXT,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(overload IN (0,1)),
    UNIQUE (nat_id, nat_acl_id, outside_interface),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id) REFERENCES t05_NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

CREATE TABLE t05_nat_exempt_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    route_map_id        INTEGER NOT NULL,  
    description         TEXT,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (nat_id, route_map_id),
    FOREIGN KEY (nat_id) REFERENCES t05_NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (route_map_id) REFERENCES t05_route_map_db(route_map_id) ON DELETE CASCADE
);
-- ============================================================
