-- 4. ĐỊNH TUYẾN (ROUTING)
-- ========================================================== 

-- 4a. Static Routes
CREATE TABLE t04_static_default_routes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT NOT NULL,
    next_hop_ip   TEXT NOT NULL,          
    success       INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

CREATE TABLE t04_static_routes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host          TEXT NOT NULL,
    network       TEXT NOT NULL,          
    subnet_mask   TEXT NOT NULL,          
    next_hop      TEXT NOT NULL,          
    ad            INTEGER DEFAULT 1 CHECK(ad BETWEEN 1 AND 255),
    success       INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

-- 4b. OSPF
CREATE TABLE IF NOT EXISTS t04_ospf_processes (
    ospf_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    host                     TEXT    NOT NULL,
    process_id               INTEGER NOT NULL,   
    router_id                TEXT,               
    reference_bandwidth      INTEGER,            
    passive_default          INTEGER DEFAULT 0,  
    default_originate        INTEGER DEFAULT 0,  
    default_originate_always INTEGER DEFAULT 0,  
    success                  INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(passive_default IN (0,1)),
    CHECK(default_originate IN (0,1)),
    CHECK(default_originate_always IN (0,1)),
    UNIQUE (host, process_id),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_networks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL,
    network     TEXT    NOT NULL,   
    wildcard    TEXT    NOT NULL,   
    area        INTEGER NOT NULL,   
    success     INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (ospf_id, network, wildcard, area),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_distance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL UNIQUE,
    external    INTEGER,    
    intra_area  INTEGER,    
    inter_area  INTEGER,    
    success     INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_areas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL,
    area_id         INTEGER NOT NULL,   
    area_type       TEXT    DEFAULT 'normal' CHECK(area_type IN ('normal','stub','nssa')),
    no_summary      INTEGER DEFAULT 0,  
    authentication  TEXT CHECK(authentication IN (NULL,'plain','message-digest')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(no_summary IN (0,1)),
    CHECK(no_summary = 0 OR area_type IN ('stub','nssa')),  -- no_summary chỉ có nghĩa với stub/nssa (totally-stubby)
    UNIQUE (ospf_id, area_id),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_area_ranges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    area_db_id  INTEGER NOT NULL,   
    ip          TEXT    NOT NULL,   
    mask        TEXT    NOT NULL,   
    advertise   INTEGER DEFAULT 1,  
    cost        INTEGER,            
    success     INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(advertise IN (0,1)),
    UNIQUE (area_db_id, ip, mask),
    FOREIGN KEY (area_db_id) REFERENCES t04_ospf_areas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_redistribute (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id     INTEGER NOT NULL,
    protocol    TEXT    NOT NULL CHECK(protocol IN ('static','connected','eigrp','bgp','rip','isis')),
    process_id  INTEGER,            
    subnets     INTEGER DEFAULT 1,  
    metric      INTEGER,            
    metric_type INTEGER CHECK(metric_type IN (NULL,1,2)),
    route_map   TEXT,               
    success     INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(subnets IN (0,1)),
    UNIQUE (ospf_id, protocol, process_id),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_passive_interfaces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ospf_id         INTEGER NOT NULL,
    interface_name      TEXT    NOT NULL,
    passive         INTEGER DEFAULT 1,  
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    CHECK(passive IN (0,1)),
    UNIQUE (ospf_id, interface_name),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t04_ospf_tuning (
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
    CHECK(success IN (-1,0,1)),
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

-- Nguồn dữ liệu duy nhất cho cấu hình OSPF per-interface.
CREATE TABLE IF NOT EXISTS t04_router_iface_ospf (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    ospf_id         INTEGER NOT NULL,               
    area            INTEGER NOT NULL DEFAULT 0,
    cost            INTEGER,
    priority        INTEGER DEFAULT 1 CHECK(priority BETWEEN 0 AND 255),
    hello_interval  INTEGER DEFAULT 10,
    dead_interval   INTEGER DEFAULT 40,
    mtu_ignore      INTEGER DEFAULT 0 CHECK(mtu_ignore IN (0,1)),
    bfd             INTEGER DEFAULT 0 CHECK(bfd IN (0,1)),
    network_type    TEXT CHECK(network_type IN (NULL,'broadcast','non-broadcast','point-to-point','point-to-multipoint')),
    auth_type       TEXT CHECK(auth_type IN (NULL,'plain','message-digest')),
    auth_key        TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id, ospf_id),
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

-- 4c. EIGRP
-- EIGRP process action logic:
--   * action: INTEGER compatibility field, default 15
--   * action_Cfg: TEXT binary string length 7, default '1111111'
--   * use action only for backward compatibility; prefer action_Cfg when supported
--   * change as_number or identity fields by replace (success = -1 + new row success = 0)
--   * change process-level overrideable options by updating row and action_Cfg
--   * child row tables use success independently.
CREATE TABLE t04_eigrp_processes (
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
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_networks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    network           TEXT NOT NULL,       
    wildcard          TEXT,                
    interface_name        TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, network, wildcard, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);

-- Nguồn dữ liệu duy nhất cho cấu hình EIGRP per-interface.
CREATE TABLE t04_router_iface_eigrp (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id          INTEGER NOT NULL,
    eigrp_id          INTEGER NOT NULL,

    bandwidth         INTEGER,
    delay             INTEGER,
    hello_interval    INTEGER,
    hold_time         INTEGER,

    split_horizon     INTEGER DEFAULT 1,
    next_hop_self     INTEGER DEFAULT 0,
    bandwidth_percent INTEGER,

    auth_key_chain    TEXT,

    summary_ip        TEXT,
    summary_mask      TEXT,

    bfd               INTEGER DEFAULT 0,
    bfd_tx            INTEGER,
    bfd_rx            INTEGER,
    bfd_multiplier    INTEGER,

    success           INTEGER DEFAULT 0,

    CHECK(split_horizon IN (0,1)),
    CHECK(next_hop_self IN (0,1)),
    CHECK(bfd IN (0,1)),
    CHECK(success IN (-1,0,1)),

    UNIQUE (iface_id, eigrp_id),

    FOREIGN KEY (iface_id)
        REFERENCES t02_interface_name(iface_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (eigrp_id)
        REFERENCES t04_eigrp_processes(eigrp_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_passive_interfaces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    interface_name        TEXT NOT NULL,
    mode              TEXT NOT NULL CHECK(mode IN ('passive','no-passive')),
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, interface_name, mode),
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_distribute_lists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    list_name         TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK(direction IN ('in','out')),
    interface_name        TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, list_name, direction, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_offset_lists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    list_name         TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK(direction IN ('in','out')),
    value             INTEGER NOT NULL,
    interface_name        TEXT,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, list_name, direction, value, interface_name),
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_redistribute (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    eigrp_id          INTEGER NOT NULL,
    protocol          TEXT NOT NULL CHECK(protocol IN ('static','connected','ospf','bgp','rip','isis')),
    route_map         TEXT,
    metric_bw         INTEGER,
    metric_delay      INTEGER,
    metric_reliability INTEGER,
    metric_load       INTEGER,
    metric_mtu        INTEGER,
    success           INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE (eigrp_id, protocol, route_map),
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);

CREATE TABLE t04_eigrp_key_chains (
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
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
);
-- ==========================================================
