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
