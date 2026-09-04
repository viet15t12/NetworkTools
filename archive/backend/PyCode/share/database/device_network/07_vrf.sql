-- 7. VRF (VIRTUAL ROUTING & FORWARDING)
-- ============================================================

PRAGMA foreign_keys = ON;

-- 7a. VRF chính
CREATE TABLE IF NOT EXISTS t07_vrf_db (
    vrf_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host            TEXT    NOT NULL,
    vrf_name        TEXT    NOT NULL,
    description     TEXT,
    rd              TEXT,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(host, vrf_name),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 7b. Route Target (import / export)
CREATE TABLE IF NOT EXISTS t07_vrf_route_target (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    rt_value        TEXT    NOT NULL,
    direction       TEXT    NOT NULL CHECK(direction IN ('import','export','both')),
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, rt_value, direction),
    FOREIGN KEY (vrf_id) REFERENCES t07_vrf_db(vrf_id) ON DELETE CASCADE
);

-- 7c. Gán Interface vào VRF (ip vrf forwarding <name>)
CREATE TABLE IF NOT EXISTS t07_vrf_interface (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    iface_id        INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(iface_id),
    FOREIGN KEY (vrf_id)   REFERENCES t07_vrf_db(vrf_id)          ON DELETE CASCADE,
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- 7d. Static Route per-VRF  (ip route vrf <name> ...)
CREATE TABLE IF NOT EXISTS t07_vrf_static_routes (
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
    FOREIGN KEY (vrf_id) REFERENCES t07_vrf_db(vrf_id) ON DELETE CASCADE
);

-- 7e. BGP Address-Family per-VRF
CREATE TABLE IF NOT EXISTS t07_vrf_bgp_af (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id              INTEGER NOT NULL,
    bgp_process_id      INTEGER NOT NULL,
    redistribute_connected INTEGER DEFAULT 0 CHECK(redistribute_connected IN (0,1)),
    redistribute_static    INTEGER DEFAULT 0 CHECK(redistribute_static    IN (0,1)),
    success             INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, bgp_process_id),
    FOREIGN KEY (vrf_id) REFERENCES t07_vrf_db(vrf_id) ON DELETE CASCADE
    -- FOREIGN KEY (bgp_process_id) REFERENCES bgp_processes(bgp_id) ON DELETE CASCADE
);

-- 7f. OSPF per-VRF  (router ospf <pid> vrf <name>)
CREATE TABLE IF NOT EXISTS t07_vrf_ospf (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    ospf_id         INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, ospf_id),
    FOREIGN KEY (vrf_id)  REFERENCES t07_vrf_db(vrf_id)        ON DELETE CASCADE,
    FOREIGN KEY (ospf_id) REFERENCES t04_ospf_processes(ospf_id) ON DELETE CASCADE
);

-- 7g. EIGRP per-VRF  (router eigrp <as> / address-family ipv4 vrf <name>)
CREATE TABLE IF NOT EXISTS t07_vrf_eigrp (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vrf_id          INTEGER NOT NULL,
    eigrp_id        INTEGER NOT NULL,
    success         INTEGER DEFAULT 0,
    CHECK(success IN (-1,0,1)),
    UNIQUE(vrf_id, eigrp_id),
    FOREIGN KEY (vrf_id)   REFERENCES t07_vrf_db(vrf_id)           ON DELETE CASCADE,
    FOREIGN KEY (eigrp_id) REFERENCES t04_eigrp_processes(eigrp_id) ON DELETE CASCADE
);
