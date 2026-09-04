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
