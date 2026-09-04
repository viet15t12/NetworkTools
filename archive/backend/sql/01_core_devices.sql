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
