"""Non-destructive FHRP schema upgrades for existing workspaces."""

from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3


_MEMBER_TABLE_SQL = """
CREATE TABLE t08_fhrp_members_new (
    member_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    fhrp_id         INTEGER NOT NULL,
    host            TEXT    NOT NULL,
    iface_id        INTEGER NOT NULL,
    interface_kind  TEXT    NOT NULL DEFAULT 'router'
                            CHECK(interface_kind IN ('router','svi')),
    priority        INTEGER NOT NULL DEFAULT 100 CHECK(priority BETWEEN 1 AND 255),
    preempt         INTEGER NOT NULL DEFAULT 0 CHECK(preempt IN (0,1)),
    shutdown        INTEGER NOT NULL DEFAULT 0 CHECK(shutdown IN (0,1)),
    sync_status     TEXT NOT NULL DEFAULT 'pending_apply'
                    CHECK(sync_status IN ('pending_apply','pending_delete','synchronized','skipped')),
    delete_restore_status TEXT
                    CHECK(delete_restore_status IS NULL OR delete_restore_status IN ('pending_apply','synchronized','skipped')),
    UNIQUE(fhrp_id, host),
    UNIQUE(fhrp_id, interface_kind, iface_id),
    FOREIGN KEY (fhrp_id) REFERENCES t08_fhrp_groups(fhrp_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (host) REFERENCES t01_devices(host)
        ON UPDATE CASCADE ON DELETE CASCADE
);
"""


_MEMBER_OBJECTS_SQL = """
CREATE INDEX ix_t08_fhrp_members_host ON t08_fhrp_members(host);
CREATE INDEX ix_t08_fhrp_members_iface
    ON t08_fhrp_members(interface_kind, iface_id);

CREATE TRIGGER trg_t08_member_iface_host_insert
BEFORE INSERT ON t08_fhrp_members
FOR EACH ROW
WHEN NEW.interface_kind = 'router' AND NOT EXISTS (
    SELECT 1 FROM t02_interface_name AS i
    WHERE i.iface_id = NEW.iface_id AND i.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP interface does not belong to host');
END;

CREATE TRIGGER trg_t08_member_svi_host_insert
BEFORE INSERT ON t08_fhrp_members
FOR EACH ROW
WHEN NEW.interface_kind = 'svi' AND NOT EXISTS (
    SELECT 1 FROM t06_svi_interface AS s
    WHERE s.id = NEW.iface_id AND s.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP SVI does not belong to host');
END;

CREATE TRIGGER trg_t08_member_iface_host_update
BEFORE UPDATE OF host, iface_id, interface_kind ON t08_fhrp_members
FOR EACH ROW
WHEN NEW.interface_kind = 'router' AND NOT EXISTS (
    SELECT 1 FROM t02_interface_name AS i
    WHERE i.iface_id = NEW.iface_id AND i.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP interface does not belong to host');
END;

CREATE TRIGGER trg_t08_member_svi_host_update
BEFORE UPDATE OF host, iface_id, interface_kind ON t08_fhrp_members
FOR EACH ROW
WHEN NEW.interface_kind = 'svi' AND NOT EXISTS (
    SELECT 1 FROM t06_svi_interface AS s
    WHERE s.id = NEW.iface_id AND s.host = NEW.host
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP SVI does not belong to host');
END;

CREATE TRIGGER trg_t08_member_endpoint_group_unique
BEFORE INSERT ON t08_fhrp_members
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM t08_fhrp_groups AS wanted
    JOIN t08_fhrp_members AS existing
      ON existing.host = NEW.host
     AND existing.interface_kind = NEW.interface_kind
     AND existing.iface_id = NEW.iface_id
    JOIN t08_fhrp_groups AS current ON current.fhrp_id = existing.fhrp_id
    WHERE wanted.fhrp_id = NEW.fhrp_id
      AND current.fhrp_id <> wanted.fhrp_id
      AND current.protocol = wanted.protocol
      AND current.group_number = wanted.group_number
)
BEGIN
    SELECT RAISE(ABORT, 'FHRP protocol/group already exists on interface');
END;

CREATE TRIGGER trg_t08_router_endpoint_delete_guard
BEFORE DELETE ON t02_interface_name
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM t08_fhrp_members
    WHERE interface_kind = 'router' AND iface_id = OLD.iface_id
)
AND EXISTS (SELECT 1 FROM t01_devices WHERE host = OLD.host)
BEGIN
    SELECT RAISE(ABORT, 'Remove FHRP group before deleting router interface');
END;

CREATE TRIGGER trg_t08_svi_endpoint_delete_guard
BEFORE DELETE ON t06_svi_interface
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM t08_fhrp_members
    WHERE interface_kind = 'svi' AND iface_id = OLD.id
)
AND EXISTS (SELECT 1 FROM t01_devices WHERE host = OLD.host)
BEGIN
    SELECT RAISE(ABORT, 'Remove FHRP group before deleting SVI');
END;
"""


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def ensure_schema(connection: sqlite3.Connection) -> list[str]:
    """Upgrade legacy FHRP members while preserving groups, options and tracks."""
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 't08_fhrp_members'"
    ).fetchone()
    if table is None:
        return []
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(t08_fhrp_members)")
    }
    changes: list[str] = []
    if "interface_kind" not in columns:
        managed_triggers = {
            "trg_t08_member_iface_host_insert",
            "trg_t08_member_iface_host_update",
            "trg_t08_member_svi_host_insert",
            "trg_t08_member_svi_host_update",
            "trg_t08_member_endpoint_group_unique",
            "trg_t08_router_endpoint_delete_guard",
            "trg_t08_svi_endpoint_delete_guard",
        }
        dependent_triggers = [
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type = 'trigger' AND sql IS NOT NULL
                  AND lower(sql) LIKE '%t08_fhrp_members%'
                """
            ).fetchall()
            if str(row[0]) not in managed_triggers
        ]
        connection.commit()
        foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            trigger_names = managed_triggers | {
                name for name, _sql in dependent_triggers
            }
            drop_triggers = "\n".join(
                f"DROP TRIGGER IF EXISTS {_quote_identifier(name)};"
                for name in sorted(trigger_names)
            )
            restore_triggers = "\n".join(
                sql.rstrip().rstrip(";") + ";" for _name, sql in dependent_triggers
            )
            connection.executescript(
                f"""
                BEGIN IMMEDIATE;
                {drop_triggers}
                DROP TABLE IF EXISTS t08_fhrp_members_new;
                {_MEMBER_TABLE_SQL}
                INSERT INTO t08_fhrp_members_new(
                    member_id, fhrp_id, host, iface_id, interface_kind,
                    priority, preempt, shutdown, sync_status,
                    delete_restore_status
                )
                SELECT member_id, fhrp_id, host, iface_id, 'router',
                       priority, preempt, shutdown, sync_status, NULL
                FROM t08_fhrp_members
                ;
                DROP TABLE t08_fhrp_members;
                ALTER TABLE t08_fhrp_members_new RENAME TO t08_fhrp_members;
                {_MEMBER_OBJECTS_SQL}
                {restore_triggers}
                COMMIT;
                """
            )
            changes.append("t08_fhrp_members.interface_kind")
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.execute(f"PRAGMA foreign_keys = {foreign_keys}")

    member_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(t08_fhrp_members)")
    }
    if "delete_restore_status" not in member_columns:
        connection.execute(
            """
            ALTER TABLE t08_fhrp_members
            ADD COLUMN delete_restore_status TEXT
                CHECK(delete_restore_status IS NULL OR delete_restore_status
                      IN ('pending_apply','synchronized','skipped'));
            """
        )
        changes.append("t08_fhrp_members.delete_restore_status")

    tracks_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 't08_fhrp_tracks'"
    ).fetchone()
    if tracks_table is not None:
        track_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(t08_fhrp_tracks)")
        }
        if "delete_restore_status" not in track_columns:
            connection.execute(
                """
                ALTER TABLE t08_fhrp_tracks
                ADD COLUMN delete_restore_status TEXT
                    CHECK(delete_restore_status IS NULL OR delete_restore_status
                          IN ('pending_apply','synchronized','skipped'));
                """
            )
            changes.append("t08_fhrp_tracks.delete_restore_status")

    # Previous releases stored v3 while rendering classic v2 commands. Align the
    # desired state with what those releases actually configured on Cisco IOS.
    vrrp_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 't08_vrrp_options'"
    ).fetchone()
    if vrrp_table is not None:
        cursor = connection.execute(
            "UPDATE t08_vrrp_options SET version = 2 WHERE version = 3"
        )
        if cursor.rowcount:
            changes.append("t08_vrrp_options.version")
    connection.commit()
    errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if errors:
        raise sqlite3.DatabaseError(
            f"foreign_key_check failed after FHRP schema upgrade: {errors[:5]}"
        )
    return changes


__all__ = ["ensure_schema"]
