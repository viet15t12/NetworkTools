-- ============================================================

-- 6. HỆ THỐNG QUẢN LÝ SWITCH L2 (L2 SWITCHING)
-- ============================================================

PRAGMA foreign_keys = ON;

-- Bảng VLAN chính
CREATE TABLE IF NOT EXISTS t06_vlan_db (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    host      TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    vlan_id   INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    vlan_name TEXT    NOT NULL DEFAULT '',
    state     TEXT    NOT NULL DEFAULT 'active' CHECK(state IN ('active','suspend')),
    UNIQUE(host, vlan_id)
);

-- Interface L2 trung tâm
CREATE TABLE IF NOT EXISTS t06_interface_l2 (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    host         TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    if_name      TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    mode         TEXT    NOT NULL DEFAULT 'access' CHECK(mode IN ('access','trunk','hybrid','routed')),
    admin_status TEXT    NOT NULL DEFAULT 'up' CHECK(admin_status IN ('up','down')),
    oper_status  TEXT    NOT NULL DEFAULT 'unknown' CHECK(oper_status IN ('up','down','err-disabled','unknown')),
    speed        TEXT    NOT NULL DEFAULT 'auto' CHECK(speed IN ('auto','10','100','1000','10000')),
    duplex       TEXT    NOT NULL DEFAULT 'auto' CHECK(duplex IN ('auto','full','half')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_iface ON t06_interface_l2(host, if_name);

-- Các bảng phụ thuộc interface L2
CREATE TABLE IF NOT EXISTS t06_iface_access (
    iface_id    INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    access_vlan INTEGER NOT NULL CHECK(access_vlan BETWEEN 1 AND 4094),
    voice_vlan  INTEGER          CHECK(voice_vlan  BETWEEN 1 AND 4094),
    CHECK(voice_vlan IS NULL OR voice_vlan <> access_vlan)
);

CREATE TABLE IF NOT EXISTS t06_iface_trunk (
    iface_id      INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    allowed_vlans TEXT    NOT NULL DEFAULT 'all',
    native_vlan   INTEGER NOT NULL DEFAULT 1   CHECK(native_vlan   BETWEEN 1 AND 4094),
    encapsulation TEXT    NOT NULL DEFAULT 'dot1q' CHECK(encapsulation IN ('dot1q','isl')),
    pruning_vlans TEXT    NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS t06_iface_stp (
    iface_id    INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    portfast    TEXT NOT NULL DEFAULT 'disabled' CHECK(portfast    IN ('enabled','disabled')),
    bpduguard   TEXT NOT NULL DEFAULT 'disabled' CHECK(bpduguard   IN ('enabled','disabled')),
    bpdufilter  TEXT NOT NULL DEFAULT 'disabled' CHECK(bpdufilter  IN ('enabled','disabled')),
    root_guard  TEXT NOT NULL DEFAULT 'disabled' CHECK(root_guard  IN ('enabled','disabled')),
    loop_guard  TEXT NOT NULL DEFAULT 'disabled' CHECK(loop_guard  IN ('enabled','disabled'))
);

CREATE TABLE IF NOT EXISTS t06_iface_port_security (
    iface_id    INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    max_mac     INTEGER NOT NULL DEFAULT 1,
    violation   TEXT    NOT NULL DEFAULT 'shutdown' CHECK(violation IN ('shutdown','restrict','protect')),
    sticky      INTEGER NOT NULL DEFAULT 0 CHECK(sticky IN (0,1)),
    aging_type  TEXT    NOT NULL DEFAULT 'absolute' CHECK(aging_type IN ('absolute','inactivity')),
    aging_time  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS t06_iface_qos (
    iface_id    INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    trust_mode  TEXT    NOT NULL DEFAULT 'none' CHECK(trust_mode IN ('none','cos','dscp','ip-precedence')),
    cos_value   INTEGER NOT NULL DEFAULT 0 CHECK(cos_value  BETWEEN 0 AND 7),
    dscp_value  INTEGER NOT NULL DEFAULT 0 CHECK(dscp_value BETWEEN 0 AND 63),
    policy_in   TEXT    NOT NULL DEFAULT '',
    policy_out  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS t06_iface_storm_control (
    iface_id  INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    bc_level  REAL    NOT NULL DEFAULT 20.00,
    mc_level  REAL    NOT NULL DEFAULT 20.00,
    uc_level  REAL    NOT NULL DEFAULT 80.00,
    action    TEXT    NOT NULL DEFAULT 'shutdown' CHECK(action IN ('shutdown','trap','none'))
);

CREATE TABLE IF NOT EXISTS t06_iface_monitor (
    iface_id      INTEGER PRIMARY KEY REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    in_octets     INTEGER NOT NULL DEFAULT 0,
    out_octets    INTEGER NOT NULL DEFAULT 0,
    in_errors     INTEGER NOT NULL DEFAULT 0,
    out_errors    INTEGER NOT NULL DEFAULT 0,
    in_discards   INTEGER NOT NULL DEFAULT 0,
    out_discards  INTEGER NOT NULL DEFAULT 0,
    last_flap     TEXT    NOT NULL DEFAULT 'never',
    polled_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS t06_iface_mac_table (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id   INTEGER NOT NULL REFERENCES t06_interface_l2(id) ON DELETE CASCADE,
    mac_addr   TEXT    NOT NULL,
    vlan_id    INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    mac_type   TEXT    NOT NULL DEFAULT 'dynamic' CHECK(mac_type IN ('dynamic','static','sticky','secure')),
    learned_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(iface_id, mac_addr, vlan_id)
);
CREATE INDEX IF NOT EXISTS ix_mac_iface ON t06_iface_mac_table(iface_id);

-- Cấu hình EtherChannel, STP, Security L2
CREATE TABLE IF NOT EXISTS t06_etherchannel (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    host         TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    po_number    INTEGER NOT NULL,
    protocol     TEXT    NOT NULL DEFAULT 'lacp' CHECK(protocol IN ('lacp','pagp','static')),
    mode         TEXT    NOT NULL DEFAULT 'active' CHECK(mode IN ('active','passive','desirable','auto','on')),
    member_ports TEXT    NOT NULL DEFAULT '',
    description  TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL DEFAULT 'up',
    UNIQUE(host, po_number)
);

CREATE TABLE IF NOT EXISTS t06_stp_config (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    host      TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    vlan_id   INTEGER NOT NULL,
    stp_mode  TEXT    NOT NULL DEFAULT 'rapid-pvst' CHECK(stp_mode IN ('pvst','rapid-pvst','mst')),
    priority  INTEGER NOT NULL DEFAULT 32768,
    root_role TEXT    NOT NULL DEFAULT 'none' CHECK(root_role IN ('primary','secondary','none')),
    UNIQUE(host, vlan_id)
);

CREATE TABLE IF NOT EXISTS t06_security_l2 (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    vlan_id       INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    dhcp_snooping INTEGER NOT NULL DEFAULT 0 CHECK(dhcp_snooping IN (0,1)),
    dai_enabled   INTEGER NOT NULL DEFAULT 0 CHECK(dai_enabled   IN (0,1)),
    UNIQUE(host, vlan_id)
);

CREATE TABLE IF NOT EXISTS t06_dhcp_trust_ports (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    host     TEXT    NOT NULL REFERENCES t01_devices(host) ON DELETE CASCADE,
    if_name  TEXT    NOT NULL,
    UNIQUE(host, if_name)
);

CREATE TABLE IF NOT EXISTS t06_svi_interface (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host        TEXT NOT NULL,
    vlan_id     INTEGER NOT NULL,
    ip_address  TEXT,
    subnet_mask TEXT,
    shutdown    INTEGER DEFAULT 0,
    success     INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE,
    FOREIGN KEY (host, vlan_id) REFERENCES t06_vlan_db(host, vlan_id)
);
-- ============================================================