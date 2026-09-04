-- 8. FIRST HOP REDUNDANCY PROTOCOLS (HSRP / VRRP / GLBP)
-- ============================================================
-- Mo hinh du lieu:
--   * t08_fhrp_groups: nhom gateway ao dung chung, chua protocol/group/VIP.
--   * t08_fhrp_members: cac thiet bi va interface tham gia nhom.
--   * t08_*_options: tuy chon rieng cua tung giao thuc.
--   * t08_fhrp_tracks: cac doi tuong tracking cua tung thanh vien.
--
-- Cot success dat tai member vi day la don vi cau hinh duoc day toi tung host:
--   -1 = can xoa tren thiet bi; 0 = cho day; 1 = da dong bo.
-- Khi sua virtual_ip/group_number o bang cha, tang service phai dua success
-- cua tat ca member thuoc nhom ve 0 trong cung mot transaction.

PRAGMA foreign_keys = ON;

-- 8a. Bang cha: mot nhom gateway ao logic co the gom nhieu router/interface.
CREATE TABLE IF NOT EXISTS t08_fhrp_groups (
    fhrp_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol        TEXT    NOT NULL CHECK(protocol IN ('hsrp','vrrp','glbp')),
    group_number    INTEGER NOT NULL,
    virtual_ip      TEXT    NOT NULL,
    address_family  TEXT    NOT NULL DEFAULT 'ipv4'
                            CHECK(address_family IN ('ipv4','ipv6')),
    vrf_name        TEXT    NOT NULL DEFAULT 'default',
    description     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    -- Gioi han group/VRID theo tung giao thuc.
    CHECK(
        (protocol = 'hsrp' AND group_number BETWEEN 0 AND 4095) OR
        (protocol = 'vrrp' AND group_number BETWEEN 1 AND 255) OR
        (protocol = 'glbp' AND group_number BETWEEN 0 AND 1023)
    ),
    -- GLBP tren Cisco IOS duoc thiet ke cho IPv4.
    CHECK(protocol <> 'glbp' OR address_family = 'ipv4'),
    UNIQUE(protocol, group_number, virtual_ip, address_family, vrf_name)
);

-- 8b. Bang thanh vien: host va interface tham gia nhom gateway ao.
CREATE TABLE IF NOT EXISTS t08_fhrp_members (
    member_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    fhrp_id         INTEGER NOT NULL,
    host            TEXT    NOT NULL,
    iface_id        INTEGER NOT NULL,
    priority        INTEGER NOT NULL DEFAULT 100 CHECK(priority BETWEEN 1 AND 255),
    preempt         INTEGER NOT NULL DEFAULT 0   CHECK(preempt IN (0,1)),
    shutdown        INTEGER NOT NULL DEFAULT 0   CHECK(shutdown IN (0,1)),
    success         INTEGER NOT NULL DEFAULT 0   CHECK(success IN (-1,0,1)),

    -- Mot host/interface chi xuat hien mot lan trong cung nhom logic.
    UNIQUE(fhrp_id, host),
    UNIQUE(fhrp_id, iface_id),
    FOREIGN KEY (fhrp_id) REFERENCES t08_fhrp_groups(fhrp_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (host) REFERENCES t01_devices(host)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_t08_fhrp_members_host
    ON t08_fhrp_members(host);
CREATE INDEX IF NOT EXISTS ix_t08_fhrp_members_iface
    ON t08_fhrp_members(iface_id);

-- Bao dam iface_id thuc su thuoc host duoc khai bao trong cung dong member.
CREATE TRIGGER IF NOT EXISTS trg_t08_member_iface_host_insert
BEFORE INSERT ON t08_fhrp_members
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t02_interface_name AS i
    WHERE i.iface_id = NEW.iface_id AND i.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP interface does not belong to host');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_member_iface_host_update
BEFORE UPDATE OF host, iface_id ON t08_fhrp_members
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t02_interface_name AS i
    WHERE i.iface_id = NEW.iface_id AND i.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP interface does not belong to host');
END;

-- Khong cho doi protocol khi nhom da co member/options; tao nhom moi se ro rang hon.
CREATE TRIGGER IF NOT EXISTS trg_t08_group_protocol_immutable
BEFORE UPDATE OF protocol ON t08_fhrp_groups
FOR EACH ROW
WHEN NEW.protocol <> OLD.protocol
 AND EXISTS (SELECT 1 FROM t08_fhrp_members WHERE fhrp_id = OLD.fhrp_id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change protocol of a populated FHRP group');
END;

-- 8c. Tuy chon rieng cho HSRP.
CREATE TABLE IF NOT EXISTS t08_hsrp_options (
    member_id              INTEGER PRIMARY KEY,
    version                INTEGER NOT NULL DEFAULT 2 CHECK(version IN (1,2)),
    hello_ms               INTEGER NOT NULL DEFAULT 3000 CHECK(hello_ms > 0),
    hold_ms                INTEGER NOT NULL DEFAULT 10000 CHECK(hold_ms > hello_ms),
    preempt_delay_min_sec  INTEGER NOT NULL DEFAULT 0 CHECK(preempt_delay_min_sec >= 0),
    preempt_delay_reload_sec INTEGER NOT NULL DEFAULT 0 CHECK(preempt_delay_reload_sec >= 0),
    auth_type              TEXT NOT NULL DEFAULT 'none'
                                  CHECK(auth_type IN ('none','plain','md5-key','md5-keychain')),
    auth_secret            TEXT,
    CHECK(
        (auth_type = 'none' AND auth_secret IS NULL) OR
        (auth_type <> 'none' AND auth_secret IS NOT NULL)
    ),
    FOREIGN KEY (member_id) REFERENCES t08_fhrp_members(member_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- 8d. Tuy chon rieng cho VRRP.
CREATE TABLE IF NOT EXISTS t08_vrrp_options (
    member_id              INTEGER PRIMARY KEY,
    version                INTEGER NOT NULL DEFAULT 3 CHECK(version IN (2,3)),
    advertisement_ms       INTEGER NOT NULL DEFAULT 1000 CHECK(advertisement_ms > 0),
    accept_mode            INTEGER NOT NULL DEFAULT 0 CHECK(accept_mode IN (0,1)),
    auth_type              TEXT NOT NULL DEFAULT 'none'
                                  CHECK(auth_type IN ('none','plain','md5')),
    auth_secret            TEXT,
    -- VRRPv3 khong su dung authentication field kieu VRRPv2.
    CHECK(version = 2 OR auth_type = 'none'),
    CHECK(
        (auth_type = 'none' AND auth_secret IS NULL) OR
        (auth_type <> 'none' AND auth_secret IS NOT NULL)
    ),
    FOREIGN KEY (member_id) REFERENCES t08_fhrp_members(member_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- 8e. Tuy chon rieng cho GLBP.
CREATE TABLE IF NOT EXISTS t08_glbp_options (
    member_id                  INTEGER PRIMARY KEY,
    hello_ms                   INTEGER NOT NULL DEFAULT 3000 CHECK(hello_ms > 0),
    hold_ms                    INTEGER NOT NULL DEFAULT 10000 CHECK(hold_ms > hello_ms),
    load_balancing             TEXT NOT NULL DEFAULT 'round-robin'
                                   CHECK(load_balancing IN ('round-robin','weighted','host-dependent')),
    weighting_max              INTEGER NOT NULL DEFAULT 100 CHECK(weighting_max BETWEEN 1 AND 254),
    weighting_lower            INTEGER CHECK(weighting_lower BETWEEN 1 AND 254),
    weighting_upper            INTEGER CHECK(weighting_upper BETWEEN 1 AND 254),
    forwarder_preempt          INTEGER NOT NULL DEFAULT 1 CHECK(forwarder_preempt IN (0,1)),
    forwarder_preempt_delay_sec INTEGER NOT NULL DEFAULT 30
                                      CHECK(forwarder_preempt_delay_sec >= 0),
    auth_type                  TEXT NOT NULL DEFAULT 'none'
                                   CHECK(auth_type IN ('none','plain','md5-key','md5-keychain')),
    auth_secret                TEXT,
    CHECK(weighting_lower IS NULL OR weighting_lower <= weighting_max),
    CHECK(weighting_upper IS NULL OR weighting_upper <= weighting_max),
    CHECK(weighting_lower IS NULL OR weighting_upper IS NULL OR weighting_lower <= weighting_upper),
    CHECK(
        (auth_type = 'none' AND auth_secret IS NULL) OR
        (auth_type <> 'none' AND auth_secret IS NOT NULL)
    ),
    FOREIGN KEY (member_id) REFERENCES t08_fhrp_members(member_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- 8f. Tracking dung chung. track_object co the la interface name hoac object ID.
CREATE TABLE IF NOT EXISTS t08_fhrp_tracks (
    track_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id       INTEGER NOT NULL,
    track_object    TEXT    NOT NULL,
    decrement_value INTEGER NOT NULL DEFAULT 10 CHECK(decrement_value BETWEEN 1 AND 254),
    success         INTEGER NOT NULL DEFAULT 0 CHECK(success IN (-1,0,1)),
    UNIQUE(member_id, track_object),
    FOREIGN KEY (member_id) REFERENCES t08_fhrp_members(member_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_t08_fhrp_tracks_member
    ON t08_fhrp_tracks(member_id);

-- 8g. Chan insert/update options sai protocol.
CREATE TRIGGER IF NOT EXISTS trg_t08_hsrp_protocol_insert
BEFORE INSERT ON t08_hsrp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'hsrp'
)
BEGIN
    SELECT RAISE(ABORT, 'HSRP options require an HSRP group');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_hsrp_protocol_update
BEFORE UPDATE OF member_id ON t08_hsrp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'hsrp'
)
BEGIN
    SELECT RAISE(ABORT, 'HSRP options require an HSRP group');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_vrrp_protocol_insert
BEFORE INSERT ON t08_vrrp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'vrrp'
)
BEGIN
    SELECT RAISE(ABORT, 'VRRP options require a VRRP group');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_vrrp_protocol_update
BEFORE UPDATE OF member_id ON t08_vrrp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'vrrp'
)
BEGIN
    SELECT RAISE(ABORT, 'VRRP options require a VRRP group');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_glbp_protocol_insert
BEFORE INSERT ON t08_glbp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'glbp'
)
BEGIN
    SELECT RAISE(ABORT, 'GLBP options require a GLBP group');
END;

CREATE TRIGGER IF NOT EXISTS trg_t08_glbp_protocol_update
BEFORE UPDATE OF member_id ON t08_glbp_options
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t08_fhrp_members AS m
    JOIN t08_fhrp_groups AS g ON g.fhrp_id = m.fhrp_id
    WHERE m.member_id = NEW.member_id AND g.protocol = 'glbp'
)
BEGIN
    SELECT RAISE(ABORT, 'GLBP options require a GLBP group');
END;

-- Tu dong cap nhat updated_at cua bang cha.
CREATE TRIGGER IF NOT EXISTS trg_t08_fhrp_groups_updated_at
AFTER UPDATE OF protocol, group_number, virtual_ip, address_family, vrf_name, description
ON t08_fhrp_groups
FOR EACH ROW
BEGIN
    UPDATE t08_fhrp_groups
    SET updated_at = datetime('now')
    WHERE fhrp_id = NEW.fhrp_id;
END;

-- ============================================================
