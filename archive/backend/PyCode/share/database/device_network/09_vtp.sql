-- 9. VLAN TRUNKING PROTOCOL (VTP)
-- ============================================================
-- Mo hinh du lieu:
--   * t09_vtp_domains: VTP domain dung chung (domain, version, authentication).
--   * t09_vtp_switches: cac switch tham gia domain va trang thai pruning.
--   * t09_vtp_database_modes: mode cua tung VTP database tren moi switch.
--
-- VTP khong duoc gan truc tiep vao tung interface. VTP advertisement di qua
-- cac trunk port; cau hinh trunk/pruning VLAN theo port da nam trong
-- t06_interface_l2 va t06_iface_trunk.
--
-- Cot success dat tai t09_vtp_switches vi switch la don vi duoc push cau hinh:
--   -1 = can go cau hinh; 0 = cho push; 1 = da dong bo.
-- Khi sua domain/version/password o bang cha, service phai dua success cua tat
-- ca switch thuoc domain ve 0 trong cung mot transaction.

PRAGMA foreign_keys = ON;

-- 9a. Bang cha: VTP domain logic dung chung cho cac switch.
CREATE TABLE IF NOT EXISTS t09_vtp_domains (
    vtp_domain_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name    TEXT    NOT NULL,
    version        INTEGER NOT NULL DEFAULT 2 CHECK(version IN (1,2,3)),
    password_type  TEXT    NOT NULL DEFAULT 'none'
                           CHECK(password_type IN ('none','plain','hidden','secret')),
    password_value TEXT,
    description    TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),

    CHECK(length(trim(domain_name)) BETWEEN 1 AND 32),
    CHECK(
        (password_type = 'none' AND password_value IS NULL) OR
        (password_type <> 'none' AND password_value IS NOT NULL
                                 AND length(password_value) > 0)
    ),
    -- hidden/secret la co che authentication cua VTP version 3.
    CHECK(version = 3 OR password_type IN ('none','plain')),
    UNIQUE(domain_name)
);

-- Luu y bao mat: password_value phai duoc ma hoa boi tang application truoc khi
-- ghi DB. Khong ghi password VTP dang ro vao log.

-- 9b. Moi switch chi tham gia mot VTP domain.
CREATE TABLE IF NOT EXISTS t09_vtp_switches (
    vtp_switch_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    vtp_domain_id  INTEGER NOT NULL,
    host           TEXT    NOT NULL,
    pruning        INTEGER NOT NULL DEFAULT 0 CHECK(pruning IN (0,1)),
    success        INTEGER NOT NULL DEFAULT 0 CHECK(success IN (-1,0,1)),

    UNIQUE(host),
    UNIQUE(vtp_domain_id, host),
    FOREIGN KEY (vtp_domain_id) REFERENCES t09_vtp_domains(vtp_domain_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (host) REFERENCES t01_devices(host)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_t09_vtp_switches_domain
    ON t09_vtp_switches(vtp_domain_id);

-- 9c. Mode theo database type.
-- VTP v1/v2 chi dung VLAN database. VTP v3 co the quan ly VLAN, MST va
-- database type chua biet (unknown) tuy IOS/platform.
CREATE TABLE IF NOT EXISTS t09_vtp_database_modes (
    vtp_mode_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    vtp_switch_id  INTEGER NOT NULL,
    database_type  TEXT    NOT NULL DEFAULT 'vlan'
                           CHECK(database_type IN ('vlan','mst','unknown')),
    mode           TEXT    NOT NULL DEFAULT 'server'
                           CHECK(mode IN ('server','client','transparent','off')),
    primary_server INTEGER NOT NULL DEFAULT 0 CHECK(primary_server IN (0,1)),

    CHECK(primary_server = 0 OR mode = 'server'),
    UNIQUE(vtp_switch_id, database_type),
    FOREIGN KEY (vtp_switch_id) REFERENCES t09_vtp_switches(vtp_switch_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_t09_vtp_modes_switch
    ON t09_vtp_database_modes(vtp_switch_id);

-- 9d. Kiem tra database type va primary server theo VTP version.
CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_mode_insert_validate
BEFORE INSERT ON t09_vtp_database_modes
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t09_vtp_switches AS s
    JOIN t09_vtp_domains AS d ON d.vtp_domain_id = s.vtp_domain_id
    WHERE s.vtp_switch_id = NEW.vtp_switch_id
      AND (d.version = 3 OR NEW.database_type = 'vlan')
      AND (NEW.primary_server = 0 OR d.version = 3)
)
BEGIN
    SELECT RAISE(ABORT, 'Invalid database type or primary role for VTP version');
END;

CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_mode_update_validate
BEFORE UPDATE OF vtp_switch_id, database_type, mode, primary_server
ON t09_vtp_database_modes
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM t09_vtp_switches AS s
    JOIN t09_vtp_domains AS d ON d.vtp_domain_id = s.vtp_domain_id
    WHERE s.vtp_switch_id = NEW.vtp_switch_id
      AND (d.version = 3 OR NEW.database_type = 'vlan')
      AND (NEW.primary_server = 0 OR d.version = 3)
)
BEGIN
    SELECT RAISE(ABORT, 'Invalid database type or primary role for VTP version');
END;

-- Trong mot domain VTP v3, moi database type chi co mot primary server.
CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_primary_insert_unique
BEFORE INSERT ON t09_vtp_database_modes
FOR EACH ROW
WHEN NEW.primary_server = 1
 AND EXISTS (
    SELECT 1
    FROM t09_vtp_database_modes AS m
    JOIN t09_vtp_switches AS current_switch
      ON current_switch.vtp_switch_id = m.vtp_switch_id
    JOIN t09_vtp_switches AS new_switch
      ON new_switch.vtp_switch_id = NEW.vtp_switch_id
    WHERE current_switch.vtp_domain_id = new_switch.vtp_domain_id
      AND m.database_type = NEW.database_type
      AND m.primary_server = 1
 )
BEGIN
    SELECT RAISE(ABORT, 'VTP domain already has a primary server for this database');
END;

CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_primary_update_unique
BEFORE UPDATE OF vtp_switch_id, database_type, primary_server
ON t09_vtp_database_modes
FOR EACH ROW
WHEN NEW.primary_server = 1
 AND EXISTS (
    SELECT 1
    FROM t09_vtp_database_modes AS m
    JOIN t09_vtp_switches AS current_switch
      ON current_switch.vtp_switch_id = m.vtp_switch_id
    JOIN t09_vtp_switches AS new_switch
      ON new_switch.vtp_switch_id = NEW.vtp_switch_id
    WHERE current_switch.vtp_domain_id = new_switch.vtp_domain_id
      AND m.database_type = NEW.database_type
      AND m.primary_server = 1
      AND m.vtp_mode_id <> OLD.vtp_mode_id
 )
BEGIN
    SELECT RAISE(ABORT, 'VTP domain already has a primary server for this database');
END;

-- Chan doi version neu cac mode hien tai se tro thanh khong hop le.
CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_version_update_validate
BEFORE UPDATE OF version ON t09_vtp_domains
FOR EACH ROW
WHEN NEW.version IN (1,2)
 AND EXISTS (
    SELECT 1
    FROM t09_vtp_switches AS s
    JOIN t09_vtp_database_modes AS m ON m.vtp_switch_id = s.vtp_switch_id
    WHERE s.vtp_domain_id = OLD.vtp_domain_id
      AND (m.database_type <> 'vlan' OR m.primary_server = 1)
 )
BEGIN
    SELECT RAISE(ABORT, 'Remove VTPv3 database modes/primary role before downgrade');
END;

-- Tu dong cap nhat updated_at cua bang cha.
CREATE TRIGGER IF NOT EXISTS trg_t09_vtp_domains_updated_at
AFTER UPDATE OF domain_name, version, password_type, password_value, description
ON t09_vtp_domains
FOR EACH ROW
BEGIN
    UPDATE t09_vtp_domains
    SET updated_at = datetime('now')
    WHERE vtp_domain_id = NEW.vtp_domain_id;
END;

-- ============================================================
