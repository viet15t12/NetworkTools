-- 1. HỆ THỐNG THIẾT BỊ CỐT LÕI (CORE DEVICES)
-- ========================================================== 
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE t01_devices (
    host        TEXT PRIMARY KEY,
    device_name TEXT,
    method      TEXT,
    portnumber  INTEGER,
    username    TEXT,
    password    TEXT,
    os          TEXT,
    role        TEXT, -- rou sw2 sw3 
    device_type TEXT DEFAULT 'unknown',
    success     INTEGER DEFAULT 0,
    t01_yangcfg INTEGER DEFAULT 0,
    dev         INTEGER DEFAULT 0
);

CREATE TABLE t01_yangcfg (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host        TEXT NOT NULL,
    username    TEXT,
    password    TEXT,
    success     INTEGER DEFAULT 0,
    FOREIGN KEY (host) REFERENCES t01_devices(host) ON UPDATE CASCADE ON DELETE CASCADE
);
-- ==========================================================
