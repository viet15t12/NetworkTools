from __future__ import annotations

from infrastructure.database import sqlcipher as sqlite3
from contextlib import closing
from typing import Any


_SUCCESS_TABLES = (
    "t06_vlan_db",
    "t06_interface_l2",
    "t06_etherchannel",
    "t06_stp_config",
    "t06_security_l2",
    "t06_dhcp_trust_ports",
    "t06_iface_mac_table",
    "t06_iface_port_security",
    "t09_vtp_switches",
)

# These entities can be edited and later deleted.  Presence is kept separately
# from ``pending_apply`` so an edited synchronized row is not mistaken for a
# brand-new local draft.
_PRESENCE_TABLES = {
    "t06_vlan_db": "success",
    "t06_etherchannel": "success",
    "t06_svi_interface": "sync_status",
}


def ensure_switch_schema(db: Any) -> None:
    """Add switch schema extensions without replacing existing data."""
    marker = str(getattr(db, "db_path", getattr(db, "path", "")) or "")
    if marker and getattr(db, "_switch_success_schema_ready", None) == marker:
        return
    all_success_tables_present = False
    with closing(db._connect()) as conn:
        with conn:
            def table_exists(table: str) -> bool:
                return conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?;",
                    (table,),
                ).fetchone() is not None

            def columns(table: str) -> set[str]:
                return {
                    str(row["name"])
                    for row in conn.execute(f"PRAGMA table_info({table});").fetchall()
                }

            def add_success_column(table: str) -> None:
                if not table_exists(table) or "success" in columns(table):
                    return
                conn.execute(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN success TEXT NOT NULL DEFAULT 'pending_apply'
                    CHECK(success IN (
                        'pending_apply','pending_delete','synchronized','skipped'
                    ));
                    """
                )

            def add_presence_column(table: str, status_column: str) -> None:
                if not table_exists(table) or "device_present" in columns(table):
                    return
                conn.execute(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN device_present INTEGER NOT NULL DEFAULT 0
                    CHECK(device_present IN (0,1));
                    """
                )
                # Existing synchronized rows came from a successful Push or
                # device pull and therefore already exist on the switch.
                conn.execute(
                    f"UPDATE {table} SET device_present = 1 "
                    f"WHERE {status_column} = 'synchronized';"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS t06_switch_l3_config (
                    host TEXT PRIMARY KEY,
                    ip_routing INTEGER NOT NULL DEFAULT 0 CHECK(ip_routing IN (0,1)),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    sync_status TEXT NOT NULL DEFAULT 'pending_apply'
                        CHECK(sync_status IN (
                            'pending_apply','pending_delete','synchronized','skipped'
                        )),
                    FOREIGN KEY (host) REFERENCES t01_devices(host) ON DELETE CASCADE
                );
                """
            )
            if "sync_status" not in columns("t06_switch_l3_config"):
                conn.execute(
                    """
                    ALTER TABLE t06_switch_l3_config
                    ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_apply'
                    CHECK(sync_status IN (
                        'pending_apply','pending_delete','synchronized','skipped'
                    ));
                    """
                )
            port_security_table_exists = table_exists("t06_iface_port_security")
            port_security_had_success = False
            if port_security_table_exists:
                port_security_columns = columns("t06_iface_port_security")
                port_security_had_success = "success" in port_security_columns
                if "enabled" not in port_security_columns:
                    conn.execute(
                        """
                        ALTER TABLE t06_iface_port_security
                        ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1
                        CHECK(enabled IN (0,1));
                        """
                    )
                if "sync_status" not in port_security_columns:
                    conn.execute(
                        """
                        ALTER TABLE t06_iface_port_security
                        ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_apply'
                        CHECK(sync_status IN (
                            'pending_apply','pending_delete','synchronized','skipped'
                        ));
                        """
                    )
            vtp_had_success = (
                table_exists("t09_vtp_switches")
                and "success" in columns("t09_vtp_switches")
            )
            for table in _SUCCESS_TABLES:
                add_success_column(table)
            for table, status_column in _PRESENCE_TABLES.items():
                add_presence_column(table, status_column)
            if (
                table_exists("t06_etherchannel")
                and "cleanup_member_ports" not in columns("t06_etherchannel")
            ):
                conn.execute(
                    """
                    ALTER TABLE t06_etherchannel
                    ADD COLUMN cleanup_member_ports TEXT NOT NULL DEFAULT '';
                    """
                )
            all_success_tables_present = all(
                table_exists(table) and "success" in columns(table)
                for table in _SUCCESS_TABLES
            ) and "sync_status" in columns("t06_switch_l3_config") and all(
                table_exists(table) and "device_present" in columns(table)
                for table in _PRESENCE_TABLES
            ) and "cleanup_member_ports" in columns("t06_etherchannel")
            if port_security_table_exists and not port_security_had_success:
                conn.execute(
                    """
                    UPDATE t06_iface_port_security
                    SET enabled = 1,
                        success = COALESCE(sync_status, 'pending_apply');
                    """
                )
            if table_exists("t09_vtp_switches") and not vtp_had_success:
                conn.execute(
                    """
                    UPDATE t09_vtp_switches
                    SET success = COALESCE(sync_status, 'pending_apply');
                    """
                )
            # Bang trang thai module cua project cu (neu co) khong con duoc
            # tao/ghi/doc; trang thai push SWL2 nam tren cot success tung row.
            duplicate = conn.execute(
                """
                SELECT host, vlan_id
                FROM t06_svi_interface
                GROUP BY host, vlan_id
                HAVING COUNT(*) > 1
                LIMIT 1;
                """
            ).fetchone()
            if duplicate is not None:
                raise sqlite3.IntegrityError(
                    "Cannot enforce unique SVI host/VLAN values while duplicate rows exist"
                )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_t06_svi_host_vlan "
                "ON t06_svi_interface(host, vlan_id);"
            )
    if marker and all_success_tables_present:
        try:
            setattr(db, "_switch_success_schema_ready", marker)
        except (AttributeError, TypeError):
            pass
