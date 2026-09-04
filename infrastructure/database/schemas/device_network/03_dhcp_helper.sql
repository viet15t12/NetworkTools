-- 3. DỊCH VỤ IP (DHCP & HELPER)
-- ========================================================== 

-- DHCP pool action_Cfg logic:
--   * type: TEXT binary string, default '111'
--   * bit2 = defaut (default-router), bit1 = dns, bit0 = lease
--   * change pool/network/subnetmask by replace (sync_status = 'pending_delete' + new row sync_status = 'pending_apply')
--   * change defaut/dns/lease by updating row and setting action_Cfg
-- t03_excluded_address only uses sync_status.
CREATE TABLE t03_dhcp_pool (
    dhcp_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    host       TEXT    NOT NULL,
    pool       TEXT    NOT NULL,
    network    TEXT    NOT NULL,
    subnetmask TEXT    NOT NULL,
    defaut     TEXT,
    dns        TEXT,
    lease      TEXT DEFAULT '1',  
    sync_status    TEXT NOT NULL DEFAULT 'pending_apply',
    action_Cfg TEXT DEFAULT '111',  
    CHECK(sync_status IN ('pending_apply','pending_delete','synchronized','skipped')),
    CHECK(length(action_Cfg) = 3 AND action_Cfg GLOB '[01][01][01]'),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE t03_excluded_address (
    ex_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    host     TEXT    NOT NULL,
    start_ip TEXT    NOT NULL,
    end_ip   TEXT    NOT NULL,
    sync_status  TEXT NOT NULL DEFAULT 'pending_apply',
    CHECK(sync_status IN ('pending_apply','pending_delete','synchronized','skipped')),
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS t03_router_iface_helper (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iface_id        INTEGER NOT NULL,
    helper_ip       TEXT    NOT NULL,               
    sync_status         TEXT NOT NULL DEFAULT 'pending_apply',
    CHECK(sync_status IN ('pending_apply','pending_delete','synchronized','skipped')),
    UNIQUE(iface_id, helper_ip),
    FOREIGN KEY (iface_id) REFERENCES t02_interface_name(iface_id) ON UPDATE CASCADE ON DELETE CASCADE
);
-- ==========================================================
