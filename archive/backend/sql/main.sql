-- ========================================================== 
-- File: 01_core_devices.sql 
-- ========================================================== 
-- ========================================================== 
-- 1. HỆ THỐNG THIẾT BỊ CỐT LÕI (CORE DEVICES)
-- ========================================================== 
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE devices (
    host        TEXT PRIMARY KEY,
    device_name TEXT,
    method      TEXT,
    portnumber  INTEGER,
    username    TEXT,
    password    TEXT,
    os          TEXT,
    role        TEXT, -- rou sw2 sw3 
    success     INTEGER DEFAULT 0,
    yangcfg     INTEGER DEFAULT 0
);

CREATE TABLE yangcfg (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host        TEXT NOT NULL,
    username    TEXT,
    password    TEXT,
    success     INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);
 
 
-- ========================================================== 
-- File: 02_interface_router_l3.sql 
-- ========================================================== 
-- ========================================================== 
-- 2. QUẢN LÝ INTERFACE (ROUTER / LAYER 3)
-- ========================================================== 

-- interface_name: no action_Cfg; description and shutdown use normal success semantics
--             and should be managed as row-level config changes.
CREATE TABLE interface_name (
    iface_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    host            TEXT    NOT NULL,
    interface_name  TEXT    NOT NULL,     
    ip_address      TEXT,                 
    subnet_mask     TEXT,                 
    description     TEXT,
    shutdown        INTEGER DEFAULT 0,    
    success         INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Mở rộng interface Layer 3
-- router_iface_l3 action_Cfg logic:
--   * type: TEXT binary string, default '11111'
--   * 5 bits: speed|duplex|negotiation|ip_flags|secondary
--   * used to override option groups without replacing the whole row
--   * core identity changes still follow success replace semantics
CREATE TABLE IF NOT EXISTS router_iface_l3 (
    iface_id        INTEGER PRIMARY KEY,            
    secondary_ip    TEXT,                           
    secondary_mask  TEXT,
    mtu             INTEGER DEFAULT 1500,           
    bandwidth       INTEGER,                        
    delay           INTEGER,                        
    -- Physical line settings
    speed           TEXT    DEFAULT 'auto' CHECK(speed IN ('auto','10','100','1000','10000')),
    duplex          TEXT    DEFAULT 'auto' CHECK(duplex IN ('auto','full','half')),
    negotiation     INTEGER DEFAULT 1     CHECK(negotiation IN (0,1)),  -- 0 = nonegotiate (tắt autoneg)
    -- L3 flags
    proxy_arp       INTEGER DEFAULT 1 CHECK(proxy_arp IN (0,1)),
    unreachables    INTEGER DEFAULT 1 CHECK(unreachables IN (0,1)),
    directed_broadcast INTEGER DEFAULT 0 CHECK(directed_broadcast IN (0,1)),
    success         INTEGER DEFAULT 0,
    action_Cfg      TEXT DEFAULT '11111',             -- binary string: speed|duplex|negotiation|ip_flags|secondary
    CHECK(success IN (-1,0,1)),
    CHECK(length(action_Cfg) = 5 AND action_Cfg GLOB '[01][01][01][01][01]'),
    CHECK(mtu IS NULL OR mtu BETWEEN 68 AND 65535),
    CHECK(bandwidth IS NULL OR bandwidth > 0),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Subinterface (dot1q)
-- router_iface_subif has no action_Cfg; changes use standard success-state semantics
CREATE TABLE IF NOT EXISTS router_iface_subif (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_iface_id INTEGER NOT NULL,               
    host            TEXT    NOT NULL,
    subif_name      TEXT    NOT NULL,               
    encapsulation   TEXT    NOT NULL DEFAULT 'dot1q' CHECK(encapsulation IN ('dot1q','isl')),
    vlan_id         INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    native          INTEGER DEFAULT 0 CHECK(native IN (0,1)),
    ip_address      TEXT,
    subnet_mask     TEXT,
    shutdown        INTEGER DEFAULT 0 CHECK(shutdown IN (0,1)),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(host, subif_name),
    FOREIGN KEY (parent_iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

-- Tunnel Interface (GRE/IPsec)
-- router_iface_tunnel action_Cfg logic: TEXT binary string default '111', direct override of tunnel-related options
CREATE TABLE IF NOT EXISTS router_iface_tunnel (
    iface_id        INTEGER PRIMARY KEY,
    tunnel_mode     TEXT    NOT NULL DEFAULT 'gre' CHECK(tunnel_mode IN ('gre','ipip','ipsec','gre-ipsec')),
    tunnel_src      TEXT    NOT NULL,               
    tunnel_dst      TEXT    NOT NULL,               
    tunnel_key      INTEGER,                        
    keepalive_sec   INTEGER,                        
    keepalive_retry INTEGER,
    ipsec_profile   TEXT,                           
    success         INTEGER DEFAULT 0,
    action_Cfg      TEXT DEFAULT '111',
    CHECK(success IN (-1,0,1)),
    CHECK(length(action_Cfg) = 3 AND action_Cfg GLOB '[01][01][01]'),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- WAN Parameters (PPPoE, Serial)
-- router_iface_wan action_Cfg logic: TEXT binary string default '11', direct override of WAN option groups
CREATE TABLE IF NOT EXISTS router_iface_wan (
    iface_id            INTEGER PRIMARY KEY,
    encap_type          TEXT    NOT NULL DEFAULT 'none' CHECK(encap_type IN ('none','pppoe','hdlc','ppp','frame-relay')),
    pppoe_dialer_pool   INTEGER,                    
    ppp_auth            TEXT CHECK(ppp_auth IN (NULL,'pap','chap')),
    ppp_username        TEXT,
    ppp_password        TEXT,
    clock_rate          INTEGER,                    
    lmi_type            TEXT CHECK(lmi_type IN (NULL,'cisco','ansi','q933a')),
    success             INTEGER DEFAULT 0,
    action_Cfg          TEXT DEFAULT '11',
    CHECK(success IN (-1,0,1)),
    CHECK(length(action_Cfg) = 2 AND action_Cfg GLOB '[01][01]'),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- QoS trên Interface
-- router_iface_qos action_Cfg logic: TEXT binary string default '111', direct override of QoS option groups
CREATE TABLE IF NOT EXISTS router_iface_qos (
    iface_id        INTEGER PRIMARY KEY,
    trust_mode      TEXT    NOT NULL DEFAULT 'none' CHECK(trust_mode IN ('none','cos','dscp','ip-precedence')),
    policy_in       TEXT,                           
    policy_out      TEXT,                           
    shape_rate      INTEGER,                        
    police_rate     INTEGER,                        
    police_burst    INTEGER,                        
    success         INTEGER DEFAULT 0,
    action_Cfg      TEXT DEFAULT '111',              
    CHECK(success IN (-1,0,1)),
    CHECK(length(action_Cfg) = 3 AND action_Cfg GLOB '[01][01][01]'),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);
 
 
-- ========================================================== 
-- File: 03_dhcp_helper.sql 
-- ========================================================== 
-- ========================================================== 
-- 3. DỊCH VỤ IP (DHCP & HELPER)
-- ========================================================== 

-- DHCP pool action_Cfg logic:
--   * type: TEXT binary string, default '111'
--   * bit2 = defaut (default-router), bit1 = dns, bit0 = lease
--   * change pool/network/subnetmask by replace (success = -1 + new row success = 0)
--   * change defaut/dns/lease by updating row and setting action_Cfg
-- excluded_address only uses success.
CREATE TABLE dhcp_pool (
    dhcp_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    host       TEXT    NOT NULL,
    pool       TEXT    NOT NULL,
    network    TEXT    NOT NULL,
    subnetmask TEXT    NOT NULL,
    defaut     TEXT,
    dns        TEXT,
    lease      TEXT DEFAULT '1',  
    success    INTEGER DEFAULT 0,
    action_Cfg TEXT DEFAULT '111',  
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE excluded_address (
    ex_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    host     TEXT    NOT NULL,
    start_ip TEXT    NOT NULL,
    end_ip   TEXT    NOT NULL,
    success  INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS router_iface_helper (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    helper_ip       TEXT    NOT NULL,               
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, helper_ip),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);
 
 
-- ========================================================== 
-- File: 04_routing.sql 
-- ========================================================== 
-- ========================================================== 
-- 4. ĐỊNH TUYẾN (ROUTING)
-- ========================================================== 

-- 4a. Static Routes
CREATE TABLE static_default_routes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT NOT NULL,
    next_hop_ip   TEXT NOT NULL,          
    success       INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE static_routes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT NOT NULL,
    network       TEXT NOT NULL,          
    subnet_mask   TEXT NOT NULL,          
    next_hop      TEXT NOT NULL,          
    ad            INTEGER DEFAULT 1,      
    success       INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

-- 4b. OSPF
CREATE TABLE IF NOT EXISTS ospf_processes (
    ospf_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    host                     TEXT    NOT NULL,
    process_id               INTEGER NOT NULL,   
    router_id                TEXT,               
    reference_bandwidth      INTEGER,            
    passive_default          INTEGER DEFAULT 0,  
    default_originate        INTEGER DEFAULT 0,  
    default_originate_always INTEGER DEFAULT 0,  
    success                  INTEGER DEFAULT 0,
    UNIQUE (host, process_id),
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_networks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL,
    network     TEXT    NOT NULL,   
    wildcard    TEXT    NOT NULL,   
    area        INTEGER NOT NULL,   
    success     INTEGER DEFAULT 0,
    UNIQUE (ospf_id, network, wildcard, area),
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_distance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL UNIQUE,
    external    INTEGER,    
    intra_area  INTEGER,    
    inter_area  INTEGER,    
    success     INTEGER DEFAULT 0,
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_areas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL,
    area_id         INTEGER NOT NULL,   
    area_type       TEXT    DEFAULT 'normal' CHECK(area_type IN ('normal','stub','nssa')),
    no_summary      INTEGER DEFAULT 0,  
    authentication  TEXT CHECK(authentication IN (NULL,'plain','message-digest')),
    success         INTEGER DEFAULT 0,
    UNIQUE (ospf_id, area_id),
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_area_ranges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    area_db_id  INTEGER NOT NULL,   
    ip          TEXT    NOT NULL,   
    mask        TEXT    NOT NULL,   
    advertise   INTEGER DEFAULT 1,  
    cost        INTEGER,            
    success     INTEGER DEFAULT 0,
    UNIQUE (area_db_id, ip, mask),
    FOREIGN KEY (area_db_id) REFERENCES ospf_areas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_redistribute (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL,
    protocol    TEXT    NOT NULL CHECK(protocol IN ('static','connected','eigrp','bgp','rip','isis')),
    process_id  INTEGER,            
    subnets     INTEGER DEFAULT 1,  
    metric      INTEGER,            
    metric_type INTEGER CHECK(metric_type IN (NULL,1,2)),
    route_map   TEXT,               
    success     INTEGER DEFAULT 0,
    UNIQUE (ospf_id, protocol, process_id),
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_passive_interfaces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL,
    interface_name  TEXT    NOT NULL,   
    passive         INTEGER DEFAULT 1,  
    success         INTEGER DEFAULT 0,
    UNIQUE (ospf_id, interface_name),
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_tuning (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL UNIQUE,
    maximum_paths   INTEGER,
    max_lsa         INTEGER,
    spf_delay       INTEGER,
    spf_min_delay   INTEGER,
    spf_max_delay   INTEGER,
    lsa_delay       INTEGER,
    lsa_min_delay   INTEGER,
    lsa_max_delay   INTEGER,
    success         INTEGER DEFAULT 0,
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ospf_interface_settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL,   
    interface_name  TEXT    NOT NULL,   
    area            INTEGER NOT NULL,   
    cost            INTEGER,            
    hello_interval  INTEGER,            
    dead_interval   INTEGER,            
    mtu_ignore      INTEGER DEFAULT 0,  
    bfd             INTEGER DEFAULT 0,  
    network_type    TEXT CHECK(network_type IN (NULL,'broadcast','non-broadcast','point-to-point','point-to-multipoint')),
    auth_type       TEXT CHECK(auth_type IN (NULL,'plain','message-digest')),
    success         INTEGER DEFAULT 0,
    UNIQUE (ospf_id, interface_name, area),
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS router_iface_ospf (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    ospf_id         INTEGER NOT NULL,               
    area            INTEGER NOT NULL DEFAULT 0,
    cost            INTEGER,
    priority        INTEGER DEFAULT 1 CHECK(priority BETWEEN 0 AND 255),
    hello_interval  INTEGER DEFAULT 10,
    dead_interval   INTEGER DEFAULT 40,
    mtu_ignore      INTEGER DEFAULT 0 CHECK(mtu_ignore IN (0,1)),
    network_type    TEXT CHECK(network_type IN (NULL,'broadcast','non-broadcast','point-to-point','point-to-multipoint')),
    auth_type       TEXT CHECK(auth_type IN (NULL,'plain','message-digest')),
    auth_key        TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, ospf_id),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

-- 4c. EIGRP
-- EIGRP process action logic:
--   * action: INTEGER compatibility field, default 15
--   * action_Cfg: TEXT binary string length 7, default '1111111'
--   * use action only for backward compatibility; prefer action_Cfg when supported
--   * change as_number or identity fields by replace (success = -1 + new row success = 0)
--   * change process-level overrideable options by updating row and action_Cfg
--   * child row tables use success independently.
CREATE TABLE eigrp_processes (
    eigrp_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host              TEXT NOT NULL,
    as_number         INTEGER NOT NULL,    
    router_id         TEXT,
    timers_active_time INTEGER,
    bfd_all_interfaces INTEGER DEFAULT 0,
    auto_summary      INTEGER DEFAULT 0,   
    passive_default   INTEGER DEFAULT 0,
    metric_weights    TEXT DEFAULT "0 1 0 1 0 0",
    distance_internal INTEGER,
    distance_external INTEGER,
    variance          INTEGER,
    maximum_paths     INTEGER,
    stub_enabled      INTEGER DEFAULT 0,
    stub_options      TEXT,
    stub_leak_map     TEXT,
    action            INTEGER DEFAULT 15,
    action_Cfg        TEXT DEFAULT '1111111',
    success           INTEGER DEFAULT 0,
    CHECK(bfd_all_interfaces IN (0,1)),
    CHECK(auto_summary IN (0,1)),
    CHECK(passive_default IN (0,1)),
    CHECK(stub_enabled IN (0,1)),
    CHECK(action >= 0),
    CHECK(length(action_Cfg) = 7 AND action_Cfg GLOB '[01][01][01][01][01][01][01]'),
    CHECK(success IN (-1,0,1)),
    UNIQUE (host, as_number),
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE eigrp_networks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    network           TEXT NOT NULL,       
    wildcard          TEXT,                
    interface_name    TEXT,                
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, network, wildcard, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_interface_settings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    interface_name    TEXT NOT NULL,
    bandwidth         INTEGER,
    delay             INTEGER,
    hello_interval    INTEGER,
    hold_time         INTEGER,
    auth_key_chain    TEXT,
    summary_ip        TEXT,
    summary_mask      TEXT,
    split_horizon     INTEGER,             
    bandwidth_percent INTEGER,
    next_hop_self     INTEGER DEFAULT 0,   
    bfd               INTEGER DEFAULT 0,
    bfd_tx            INTEGER,
    bfd_rx            INTEGER,
    bfd_multiplier    INTEGER,
    success           INTEGER DEFAULT 0,
    CHECK(split_horizon IN (NULL,0,1)),
    CHECK(next_hop_self IN (0,1)),
    CHECK(bfd IN (0,1)),
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS router_iface_eigrp (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    eigrp_id        INTEGER NOT NULL,               
    bandwidth       INTEGER,                        
    delay           INTEGER,                        
    hello_interval  INTEGER,
    hold_time       INTEGER,
    split_horizon   INTEGER DEFAULT 1 CHECK(split_horizon IN (0,1)),
    auth_key_chain  TEXT,
    summary_ip      TEXT,                           
    summary_mask    TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, eigrp_id),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_passive_interfaces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    interface_name    TEXT NOT NULL,
    mode              TEXT NOT NULL CHECK(mode IN ('passive','no-passive')),
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, interface_name, mode),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_distribute_lists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    list_name         TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK(direction IN ('in','out')),
    interface_name    TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, list_name, direction, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_offset_lists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    list_name         TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK(direction IN ('in','out')),
    value             INTEGER NOT NULL,
    interface_name    TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, list_name, direction, value, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_redistribute (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    protocol          TEXT NOT NULL,        
    route_map         TEXT,
    metric_bw         INTEGER,
    metric_delay      INTEGER,
    metric_reliability INTEGER,
    metric_load       INTEGER,
    metric_mtu        INTEGER,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, protocol, route_map),
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE eigrp_key_chains (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    host              TEXT NOT NULL,
    chain_name        TEXT NOT NULL,
    key_id            INTEGER,
    key_string        TEXT,
    accept_lifetime   TEXT,
    send_lifetime     TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (host, chain_name, key_id),
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);
 
 
-- ========================================================== 
-- File: 05_security_nat.sql 
-- ========================================================== 
-- ========================================================== 
-- 5. BẢO MẬT & NAT (SECURITY, ACL & NAT)
-- ========================================================== 

-- 5a. ACL Database
-- ACL_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description / remark
--   * change acl_name or acl_type by replace (success = -1 + new row success = 0)
--   * change description by keeping row and setting action_Cfg
--   * rule child tables only use success.
CREATE TABLE ACL_DB (
    Acl_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_name     TEXT NOT NULL,           
    acl_type     TEXT NOT NULL,           
    host         TEXT NOT NULL,
    description  TEXT,                    
    success      INTEGER DEFAULT 0,       
    action_Cfg   INTEGER DEFAULT 1,       
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE standard_acl_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id      INTEGER NOT NULL,
    sequence    INTEGER,
    action      TEXT NOT NULL,            
    source      TEXT NOT NULL,            
    wildcard    TEXT,                     
    success     INTEGER DEFAULT 0,        
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE extended_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id          INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL,        
    protocol        TEXT NOT NULL,        
    source          TEXT NOT NULL,
    src_wildcard    TEXT,
    src_port        TEXT,
    destination     TEXT NOT NULL,
    dst_wildcard    TEXT,
    dst_port        TEXT,
    success         INTEGER DEFAULT 0,    
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE dynamic_acl_rules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id           INTEGER NOT NULL,
    sequence         INTEGER,
    action           TEXT NOT NULL,       
    protocol         TEXT NOT NULL,
    source           TEXT NOT NULL,
    src_wildcard     TEXT,
    src_port         TEXT,
    destination      TEXT NOT NULL,
    dst_wildcard     TEXT,
    dst_port         TEXT,
    dynamic_name     TEXT NOT NULL,       
    timeout_seconds  INTEGER DEFAULT 300,
    success          INTEGER DEFAULT 0,   
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE reflexive_acl_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id          INTEGER NOT NULL,
    sequence        INTEGER,
    action          TEXT NOT NULL,        
    protocol        TEXT NOT NULL,
    source          TEXT NOT NULL,
    src_wildcard    TEXT,
    src_port        TEXT,
    destination     TEXT NOT NULL,
    dst_wildcard    TEXT,
    dst_port        TEXT,
    reflect_name    TEXT,                 
    timeout_seconds INTEGER DEFAULT 300,
    success         INTEGER DEFAULT 0,    
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE mac_acl_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acl_id      INTEGER NOT NULL,
    sequence    INTEGER,
    action      TEXT NOT NULL,            
    src_mac     TEXT NOT NULL,
    src_mask    TEXT,
    dst_mac     TEXT,
    dst_mask    TEXT,
    ethertype   TEXT,
    success     INTEGER DEFAULT 0,        
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS router_iface_acl (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    acl_id          INTEGER NOT NULL,               
    direction       TEXT    NOT NULL CHECK(direction IN ('in','out')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, direction),                    
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (acl_id) REFERENCES ACL_DB(Acl_id) ON DELETE CASCADE
);

-- 5b. Route Map
CREATE TABLE route_map_db (
    route_map_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    route_map_name TEXT NOT NULL,
    host           TEXT NOT NULL,
    description    TEXT,
    success        INTEGER DEFAULT 0,
    UNIQUE (host, route_map_name),
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

-- 5c. NAT ACL
-- NAT_ACL_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description
--   * change acl_name or acl_type by replace (success = -1 + new row success = 0)
--   * change description by setting bit0 in action_Cfg
--   * rule child tables only use success.
CREATE TABLE NAT_ACL_DB (
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
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE route_map_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    route_map_id   INTEGER NOT NULL,
    sequence       INTEGER NOT NULL,
    action         TEXT NOT NULL CHECK(action IN ('permit','deny')),
    nat_acl_id     INTEGER,          
    success        INTEGER DEFAULT 0,
    UNIQUE (route_map_id, sequence),
    FOREIGN KEY (route_map_id) REFERENCES route_map_db(route_map_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id)   REFERENCES NAT_ACL_DB(nat_acl_id)
);

CREATE TABLE nat_standard_acl_rules (
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
    FOREIGN KEY (nat_acl_id) REFERENCES NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

CREATE TABLE nat_extended_acl_rules (
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
    FOREIGN KEY (nat_acl_id) REFERENCES NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

-- 5d. NAT Core
-- NAT_DB action_Cfg logic:
--   * type: INTEGER, default 1
--   * bit0 = description
--   * change nat_name or nat_type by replace (success = -1 + new row success = 0)
--   * change description by keeping row and setting action_Cfg
--   * NAT child tables only use success.
CREATE TABLE NAT_DB (
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
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE
);

CREATE TABLE nat_interfaces (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    interface_name      TEXT NOT NULL,
    nat_role            TEXT NOT NULL CHECK(nat_role IN ('inside','outside')),
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (nat_id, interface_name),
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS router_iface_nat (
    iface_id        INTEGER PRIMARY KEY,
    nat_role        TEXT    NOT NULL CHECK(nat_role IN ('inside','outside')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE nat_pools (
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
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE nat_static_mappings (
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
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE
);

CREATE TABLE nat_dynamic_rules (
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
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id) REFERENCES NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE,
    FOREIGN KEY (pool_id) REFERENCES nat_pools(pool_id) ON DELETE CASCADE
);

CREATE TABLE nat_overload_interface_rules (
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
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (nat_acl_id) REFERENCES NAT_ACL_DB(nat_acl_id) ON DELETE CASCADE
);

CREATE TABLE nat_exempt_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nat_id              INTEGER NOT NULL,
    route_map_id        INTEGER NOT NULL,  
    description         TEXT,
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (nat_id, route_map_id),
    FOREIGN KEY (nat_id) REFERENCES NAT_DB(nat_id) ON DELETE CASCADE,
    FOREIGN KEY (route_map_id) REFERENCES route_map_db(route_map_id) ON DELETE CASCADE
);
 
 
-- ========================================================== 
-- File: 06_l2_switching.sql 
-- ========================================================== 
-- ============================================================
-- 6. HỆ THỐNG QUẢN LÝ SWITCH L2 (L2 SWITCHING)
-- ============================================================

PRAGMA foreign_keys = ON;

-- Bảng VLAN chính
CREATE TABLE IF NOT EXISTS vlan_db (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    host      TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    vlan_id   INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    vlan_name TEXT    NOT NULL DEFAULT '',
    state     TEXT    NOT NULL DEFAULT 'active' CHECK(state IN ('active','suspend')),
    UNIQUE(host, vlan_id)
);

-- Interface L2 trung tâm
CREATE TABLE IF NOT EXISTS interface_l2 (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    host         TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    if_name      TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    mode         TEXT    NOT NULL DEFAULT 'access' CHECK(mode IN ('access','trunk','hybrid','routed')),
    admin_status TEXT    NOT NULL DEFAULT 'up' CHECK(admin_status IN ('up','down')),
    oper_status  TEXT    NOT NULL DEFAULT 'unknown' CHECK(oper_status IN ('up','down','err-disabled','unknown')),
    speed        TEXT    NOT NULL DEFAULT 'auto',
    duplex       TEXT    NOT NULL DEFAULT 'auto' CHECK(duplex IN ('auto','full','half')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_iface ON interface_l2(host, if_name);

-- Các bảng phụ thuộc interface L2
CREATE TABLE IF NOT EXISTS iface_access (
    iface_id    INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    access_vlan INTEGER NOT NULL CHECK(access_vlan BETWEEN 1 AND 4094),
    voice_vlan  INTEGER          CHECK(voice_vlan  BETWEEN 1 AND 4094)
);

CREATE TABLE IF NOT EXISTS iface_trunk (
    iface_id      INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    allowed_vlans TEXT    NOT NULL DEFAULT 'all',
    native_vlan   INTEGER NOT NULL DEFAULT 1   CHECK(native_vlan   BETWEEN 1 AND 4094),
    encapsulation TEXT    NOT NULL DEFAULT 'dot1q' CHECK(encapsulation IN ('dot1q','isl')),
    pruning_vlans TEXT    NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS iface_stp (
    iface_id    INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    portfast    TEXT NOT NULL DEFAULT 'disabled' CHECK(portfast    IN ('enabled','disabled')),
    bpduguard   TEXT NOT NULL DEFAULT 'disabled' CHECK(bpduguard   IN ('enabled','disabled')),
    bpdufilter  TEXT NOT NULL DEFAULT 'disabled' CHECK(bpdufilter  IN ('enabled','disabled')),
    root_guard  TEXT NOT NULL DEFAULT 'disabled' CHECK(root_guard  IN ('enabled','disabled')),
    loop_guard  TEXT NOT NULL DEFAULT 'disabled' CHECK(loop_guard  IN ('enabled','disabled'))
);

CREATE TABLE IF NOT EXISTS iface_port_security (
    iface_id    INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    max_mac     INTEGER NOT NULL DEFAULT 1,
    violation   TEXT    NOT NULL DEFAULT 'shutdown' CHECK(violation IN ('shutdown','restrict','protect')),
    sticky      INTEGER NOT NULL DEFAULT 0 CHECK(sticky IN (0,1)),
    aging_type  TEXT    NOT NULL DEFAULT 'absolute' CHECK(aging_type IN ('absolute','inactivity')),
    aging_time  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS iface_qos (
    iface_id    INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    trust_mode  TEXT    NOT NULL DEFAULT 'none' CHECK(trust_mode IN ('none','cos','dscp','ip-precedence')),
    cos_value   INTEGER NOT NULL DEFAULT 0 CHECK(cos_value  BETWEEN 0 AND 7),
    dscp_value  INTEGER NOT NULL DEFAULT 0 CHECK(dscp_value BETWEEN 0 AND 63),
    policy_in   TEXT    NOT NULL DEFAULT '',
    policy_out  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS iface_storm_control (
    iface_id  INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    bc_level  REAL    NOT NULL DEFAULT 20.00,
    mc_level  REAL    NOT NULL DEFAULT 20.00,
    uc_level  REAL    NOT NULL DEFAULT 80.00,
    action    TEXT    NOT NULL DEFAULT 'shutdown' CHECK(action IN ('shutdown','trap','none'))
);

CREATE TABLE IF NOT EXISTS iface_monitor (
    iface_id      INTEGER PRIMARY KEY REFERENCES interface_l2(id) ON DELETE CASCADE,
    in_octets     INTEGER NOT NULL DEFAULT 0,
    out_octets    INTEGER NOT NULL DEFAULT 0,
    in_errors     INTEGER NOT NULL DEFAULT 0,
    out_errors    INTEGER NOT NULL DEFAULT 0,
    in_discards   INTEGER NOT NULL DEFAULT 0,
    out_discards  INTEGER NOT NULL DEFAULT 0,
    last_flap     TEXT    NOT NULL DEFAULT 'never',
    polled_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS iface_mac_table (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id   INTEGER NOT NULL REFERENCES interface_l2(id) ON DELETE CASCADE,
    mac_addr   TEXT    NOT NULL,
    vlan_id    INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    mac_type   TEXT    NOT NULL DEFAULT 'dynamic' CHECK(mac_type IN ('dynamic','static','sticky','secure')),
    learned_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(iface_id, mac_addr, vlan_id)
);
CREATE INDEX IF NOT EXISTS ix_mac_iface ON iface_mac_table(iface_id);

-- Cấu hình EtherChannel, STP, Security L2
CREATE TABLE IF NOT EXISTS etherchannel (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    host         TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    po_number    INTEGER NOT NULL,
    protocol     TEXT    NOT NULL DEFAULT 'lacp' CHECK(protocol IN ('lacp','pagp','static')),
    mode         TEXT    NOT NULL DEFAULT 'active' CHECK(mode IN ('active','passive','desirable','auto','on')),
    member_ports TEXT    NOT NULL DEFAULT '',
    description  TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL DEFAULT 'up',
    UNIQUE(host, po_number)
);

CREATE TABLE IF NOT EXISTS stp_config (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    host      TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    vlan_id   INTEGER NOT NULL,
    stp_mode  TEXT    NOT NULL DEFAULT 'rapid-pvst' CHECK(stp_mode IN ('pvst','rapid-pvst','mst')),
    priority  INTEGER NOT NULL DEFAULT 32768,
    root_role TEXT    NOT NULL DEFAULT 'none' CHECK(root_role IN ('primary','secondary','none')),
    UNIQUE(host, vlan_id)
);

CREATE TABLE IF NOT EXISTS security_l2 (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    vlan_id       INTEGER NOT NULL CHECK(vlan_id BETWEEN 1 AND 4094),
    dhcp_snooping INTEGER NOT NULL DEFAULT 0 CHECK(dhcp_snooping IN (0,1)),
    dai_enabled   INTEGER NOT NULL DEFAULT 0 CHECK(dai_enabled   IN (0,1)),
    UNIQUE(host, vlan_id)
);

CREATE TABLE IF NOT EXISTS dhcp_trust_ports (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    host     TEXT    NOT NULL REFERENCES devices(host) ON DELETE CASCADE,
    if_name  TEXT    NOT NULL,
    UNIQUE(host, if_name)
);


-- sw layer3
CREATE TABLE IF NOT EXISTS svi_interface (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host        TEXT NOT NULL,
    vlan_id     INTEGER NOT NULL,
    ip_address  TEXT,
    subnet_mask TEXT,
    shutdown    INTEGER DEFAULT 0,
    success     INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES devices(host) ON DELETE CASCADE,
    FOREIGN KEY (host, vlan_id) REFERENCES vlan_db(host, vlan_id)
);
 
 
-- ========================================================== 
-- File: 07_vrf.sql 
-- ========================================================== 
-- ============================================================
-- 7. VRF (VIRTUAL ROUTING & FORWARDING)
-- ============================================================

PRAGMA foreign_keys = ON;

-- 7a. VRF chính
CREATE TABLE IF NOT EXISTS vrf_db (
    vrf_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host            TEXT    NOT NULL,
    vrf_name        TEXT    NOT NULL,
    description     TEXT,
    rd              TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(host, vrf_name),
    FOREIGN KEY (host) REFERENCES devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 7b. Route Target (import / export)
CREATE TABLE IF NOT EXISTS vrf_route_target (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    rt_value        TEXT    NOT NULL,
    direction       TEXT    NOT NULL CHECK(direction IN ('import','export','both')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, rt_value, direction),
    FOREIGN KEY (vrf_id) REFERENCES vrf_db(vrf_id) ON DELETE CASCADE
);

-- 7c. Gán Interface vào VRF (ip vrf forwarding <name>)
CREATE TABLE IF NOT EXISTS vrf_interface (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    iface_id        INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id),
    FOREIGN KEY (vrf_id)   REFERENCES vrf_db(vrf_id)          ON DELETE CASCADE,
    FOREIGN KEY (iface_id) REFERENCES interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 7d. Static Route per-VRF  (ip route vrf <name> ...)
CREATE TABLE IF NOT EXISTS vrf_static_routes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    network         TEXT    NOT NULL,
    subnet_mask     TEXT    NOT NULL,
    next_hop        TEXT    NOT NULL,
    exit_interface  TEXT,
    ad              INTEGER DEFAULT 1,
    permanent       INTEGER DEFAULT 0 CHECK(permanent IN (0,1)),
    description     TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, network, subnet_mask, next_hop),
    FOREIGN KEY (vrf_id) REFERENCES vrf_db(vrf_id) ON DELETE CASCADE
);

-- 7e. BGP Address-Family per-VRF
CREATE TABLE IF NOT EXISTS vrf_bgp_af (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id              INTEGER NOT NULL,
    bgp_process_id      INTEGER NOT NULL,
    redistribute_connected INTEGER DEFAULT 0 CHECK(redistribute_connected IN (0,1)),
    redistribute_static    INTEGER DEFAULT 0 CHECK(redistribute_static    IN (0,1)),
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, bgp_process_id),
    FOREIGN KEY (vrf_id) REFERENCES vrf_db(vrf_id) ON DELETE CASCADE
    -- FOREIGN KEY (bgp_process_id) REFERENCES bgp_processes(bgp_id) ON DELETE CASCADE
);

-- 7f. OSPF per-VRF  (router ospf <pid> vrf <name>)
CREATE TABLE IF NOT EXISTS vrf_ospf (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    ospf_id         INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, ospf_id),
    FOREIGN KEY (vrf_id)  REFERENCES vrf_db(vrf_id)        ON DELETE CASCADE,
    FOREIGN KEY (ospf_id) REFERENCES ospf_processes(ospf_id) ON DELETE CASCADE
);

-- 7g. EIGRP per-VRF  (router eigrp <as> / address-family ipv4 vrf <name>)
CREATE TABLE IF NOT EXISTS vrf_eigrp (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    eigrp_id        INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, eigrp_id),
    FOREIGN KEY (vrf_id)   REFERENCES vrf_db(vrf_id)           ON DELETE CASCADE,
    FOREIGN KEY (eigrp_id) REFERENCES eigrp_processes(eigrp_id) ON DELETE CASCADE
);
 
 
