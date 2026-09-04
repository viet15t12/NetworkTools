"""QML slots grouped by the device responsibility."""

from __future__ import annotations

import sqlite3
import sys
from typing import Any

from PyQt6.QtCore import pyqtSlot

from domain.status import ConnectionStatus, connection_status
from infrastructure.database.paths import require_database
from features.devices.classification import device_type_for_role, normalize_device_role
from features.devices.ssh_algorithm_repository import (
    clear_ssh_algorithm_override,
    get_ssh_algorithm_settings,
    save_ssh_algorithm_override,
)
from .conversion import _clean_display_text, _variant_list


class _ManagedConnection(sqlite3.Connection):
    """Commit/rollback like sqlite3.Connection and always close after ``with``."""

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        """Finish the transaction and close the managed SQLite connection."""
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


class DeviceSlotsMixin:
    """Provide the stable QML contract for this responsibility."""

    def _connect(self) -> sqlite3.Connection:
        """Return a real connection compatible with repository context styles."""
        conn = sqlite3.connect(
            require_database(self.db_path),
            timeout=10.0,
            factory=_ManagedConnection,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        """Add a compatibility column only when it is absent from a table."""
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table});")}
        if column not in columns:
            conn.execute(ddl)

    def _table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        """Return whether a named SQLite table exists in the active database."""
        row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1;
            """,
            (table,),
        ).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        """Return the column names declared by a SQLite table."""
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table});")}

    @pyqtSlot(str, result="QVariant")
    def getSshAlgorithmSettings(self, host: str) -> dict[str, Any]:
        """Return normalized per-device SSH compatibility fields for QML."""
        try:
            row = get_ssh_algorithm_settings(self.db_path, host)
            return {"ok": True, **(row or {})}
        except sqlite3.Error as exc:
            return {"ok": False, "message": str(exc)}

    @pyqtSlot(str, "QVariant", result="QVariant")
    def saveSshAlgorithmSettings(
        self, host: str, payload: Any
    ) -> dict[str, Any]:
        """Persist opt-in SSH algorithm preferences supplied by the device form."""
        return save_ssh_algorithm_override(
            self.db_path, host, self._as_dict(payload)
        )

    @pyqtSlot(str, result="QVariant")
    def resetSshAlgorithmSettings(self, host: str) -> dict[str, Any]:
        """Delete a device's SSH override so Paramiko defaults are restored."""
        return clear_ssh_algorithm_override(self.db_path, host)

    @pyqtSlot(str, result="QVariant")
    def testDeviceSsh(self, host: str) -> dict[str, Any]:
        """Test SSH with the saved device credentials and per-host override."""
        from infrastructure.network.ssh_algorithms import (
            classify_ssh_error,
            ssh_runtime_diagnostics,
        )

        target = self.getDeviceByHost(host)
        if not target:
            message = "Device was not found."
            return {
                "ok": False,
                "message": message,
                "diagnostic": ssh_runtime_diagnostics("CONNECTION_ERROR", message),
            }
        if str(target.get("protocol") or "").upper() != "SSH":
            message = "SSH test is available only for SSH devices."
            return {
                "ok": False,
                "message": message,
                "diagnostic": ssh_runtime_diagnostics("CONNECTION_ERROR", message),
            }
        from infrastructure.network.device_connector import DeviceConnector

        connector = DeviceConnector(
            host=target["ip"],
            method="ssh",
            port=target.get("port") or 22,
            username=target.get("user") or "",
            password=target.get("pass") or "",
            device_type=target.get("os") or "cisco_ios",
            db_path=self.db_path,
        )
        ok = connector.connect()
        message = "SSH connection succeeded." if ok else connector.last_error
        connector.disconnect()
        code = "OK" if ok else classify_ssh_error(RuntimeError(message))
        return {
            "ok": ok,
            "message": message,
            "diagnostic": ssh_runtime_diagnostics(code, message),
        }

    @pyqtSlot(str, result=bool)
    def testDeviceSshAsync(self, host: str) -> bool:
        """Test a device on a worker thread and emit safe diagnostics."""
        target_host = str(host or "").strip()
        if not target_host:
            self.sshTestFinished.emit(
                "", False, "Device host is required.", {}
            )
            return False
        task_key = f"ssh-test:{target_host}"

        def run_test(progress: Any) -> dict[str, Any]:
            """Execute the blocking connector test outside the QML thread."""
            progress(f"Testing SSH compatibility for {target_host}...")
            return self.testDeviceSsh(target_host)

        def finished(
            _task_key: str,
            ok: bool,
            message: str,
            result: object,
        ) -> None:
            """Relay the worker result through the stable QML signal."""
            payload = result if isinstance(result, dict) else {}
            final_ok = bool(payload.get("ok", ok))
            final_message = str(payload.get("message") or message)
            self.sshTestFinished.emit(
                target_host,
                final_ok,
                final_message,
                payload.get("diagnostic") or {},
            )
            self.taskFinished.emit(final_ok, final_message)

        return self._task_coordinator.start(
            task_key,
            f"Testing SSH for {target_host}...",
            run_test,
            on_started=self._relay_task_started,
            on_progress=self._relay_task_progress,
            on_finished=finished,
        )

    @pyqtSlot(str, str, str, str, str, str, result=bool)
    @pyqtSlot(str, str, str, str, str, str, str, str, str, result=bool)
    def addDevice(
        self,
        host: str,
        device_name: str,
        method: str,
        port_text: str,
        username: str,
        password: str,
        os_name: str = "",
        role: str = "",
        device_type: str = "",
    ) -> bool:
        """Thêm một thiết bị mới từ UI vào bảng t01_devices."""
        host = (host or "").strip()
        if not host:
            return False
        try:
            port = int(port_text) if str(port_text).strip() else None
        except ValueError:
            return False
        if port is not None and not 1 <= port <= 65535:
            return False
        role = normalize_device_role(role, device_type) or "rou"
        device_type = device_type_for_role(role)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO t01_devices
                        (host, device_name, method, portnumber, username, password, os, role, connection_status, dev, device_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, ?);
                    """,
                    (
                        host,
                        _clean_display_text(device_name) or None,
                        method or None,
                        port,
                        username or None,
                        password or None,
                        os_name or None,
                        role,
                        device_type,
                    ),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as exc:
            print(f"[db] addDevice failed: {exc}", file=sys.stderr)
            return False

    @pyqtSlot("QVariant", result="QVariant")
    def addDevicesBatch(self, payload: Any) -> dict[str, Any]:
        """Insert a validated device batch in one database transaction."""
        raw_rows = self._as_list(payload)
        if not raw_rows:
            return {
                "ok": False,
                "message": "No device rows were provided.",
                "added": 0,
                "skipped": 0,
                "devices": [],
            }

        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_rows, start=1):
            row = self._as_dict(raw)
            host = str(row.get("host") or "").strip()
            if not host:
                return {
                    "ok": False,
                    "message": f"Row {index}: Host is required.",
                    "added": 0,
                    "skipped": 0,
                    "devices": [],
                }
            try:
                port = int(str(row.get("port") or "").strip())
            except (TypeError, ValueError):
                port = 0
            if not 1 <= port <= 65535:
                return {
                    "ok": False,
                    "message": f"Row {index}: Port must be an integer in range 1-65535.",
                    "added": 0,
                    "skipped": 0,
                    "devices": [],
                }
            role = normalize_device_role(row.get("role"), row.get("type")) or "rou"
            rows.append(
                {
                    "host": host,
                    "name": _clean_display_text(row.get("name")),
                    "method": str(row.get("protocol") or row.get("method") or "SSH").strip().upper(),
                    "port": port,
                    "username": str(row.get("username") or row.get("user") or "").strip(),
                    "password": str(row.get("password") or row.get("pass") or "").strip(),
                    "os": str(row.get("os") or "cisco_ios").strip() or "cisco_ios",
                    "role": role,
                    "type": device_type_for_role(role),
                }
            )

        added_devices: list[dict[str, Any]] = []
        skipped = 0
        try:
            with self._connect() as conn:
                for row in rows:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO t01_devices
                            (host, device_name, method, portnumber, username, password,
                             os, role, connection_status, dev, device_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, ?);
                        """,
                        (
                            row["host"], row["name"] or None, row["method"] or None,
                            row["port"], row["username"] or None, row["password"] or None,
                            row["os"] or None, row["role"], row["type"],
                        ),
                    )
                    if cursor.rowcount:
                        added_devices.append(
                            {
                                "ip": row["host"], "name": row["name"],
                                "protocol": row["method"], "port": str(row["port"]),
                                "user": row["username"], "pass": row["password"],
                                "os": row["os"], "role": row["role"],
                                "status": "waiting", "type": row["type"],
                            }
                        )
                    else:
                        skipped += 1
                conn.commit()
        except sqlite3.Error as exc:
            print(f"[db] addDevicesBatch failed: {exc}", file=sys.stderr)
            return {
                "ok": False,
                "message": f"Could not add devices: {exc}",
                "added": 0,
                "skipped": 0,
                "devices": [],
            }

        added = len(added_devices)
        message = f"Added {added}/{len(rows)} devices."
        if skipped:
            message += f" Skipped {skipped} existing device(s)."
        return {
            "ok": added > 0,
            "message": message,
            "added": added,
            "skipped": skipped,
            "devices": _variant_list(added_devices),
            "foldersOk": True,
        }

    @pyqtSlot(str, result="QVariant")
    def deleteDevice(self, host: str) -> dict[str, Any]:
        """Permanently delete a host and all host-owned workspace data."""
        target_host = (host or "").strip()
        if not target_host:
            return {"ok": False, "severity": "warning", "message": "Delete device failed: host is empty."}
        try:
            info_path = require_database(self.info_db_path)
            with self._connect() as conn:
                conn.execute("ATTACH DATABASE ? AS info_db;", (str(info_path),))
                conn.execute("BEGIN IMMEDIATE;")

                exists = conn.execute(
                    "SELECT 1 FROM t01_devices WHERE host = ? LIMIT 1;",
                    (target_host,),
                ).fetchone()
                if exists is None:
                    conn.rollback()
                    return {
                        "ok": False,
                        "severity": "warning",
                        "message": f"Device {target_host} was not found.",
                    }

                info_rows = self._delete_info_rows_for_host(conn, target_host)
                cursor = conn.execute(
                    "DELETE FROM t01_devices WHERE host = ?;", (target_host,)
                )
                conn.commit()

            backup_deleted = False
            backup_service = getattr(self, "_config_backup_service", None)
            if backup_service is not None:
                backup_deleted = bool(backup_service.delete_host_data(target_host))
            return {
                "ok": cursor.rowcount == 1,
                "severity": "success",
                "message": (
                    f"Permanently deleted {target_host} and all related data "
                    f"({info_rows} collected-data row(s) removed"
                    + (", configuration backups removed)." if backup_deleted else ").")
                ),
                "deletedInfoRows": info_rows,
                "deletedBackups": backup_deleted,
            }
        except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
            print(f"[db] deleteDevice failed: {exc}", file=sys.stderr)
            return {
                "ok": False,
                "severity": "error",
                "message": f"Could not permanently delete {target_host}: {exc}",
            }

    @staticmethod
    def _delete_info_rows_for_host(
        conn: sqlite3.Connection, host: str
    ) -> int:
        """Delete direct host rows; declared foreign keys remove child rows."""
        rows = conn.execute(
            """
            SELECT name FROM info_db.sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
            """
        ).fetchall()
        deleted = 0
        for row in rows:
            table = str(row[0])
            quoted_table = table.replace('"', '""')
            columns = {
                str(column[1])
                for column in conn.execute(
                    f'PRAGMA info_db.table_info("{quoted_table}");'
                )
            }
            host_column = "device_host" if "device_host" in columns else (
                "host" if "host" in columns else ""
            )
            if not host_column:
                continue
            cursor = conn.execute(
                f'DELETE FROM info_db."{quoted_table}" WHERE "{host_column}" = ?;',
                (host,),
            )
            deleted += max(0, cursor.rowcount)
        return deleted

    @pyqtSlot(str, str, result=bool)
    def updateDeviceConnectionStatus(self, host: str, status: str) -> bool:
        """Update a device connection status."""
        target_host = (host or "").strip()
        if not target_host:
            return False
        try:
            normalized = connection_status(status)
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE t01_devices SET connection_status = ? WHERE host = ?;",
                    (normalized.value, target_host),
                )
                conn.commit()
            if cursor.rowcount <= 0:
                return False
            return True
        except (sqlite3.Error, ValueError) as exc:
            print(f"[db] updateDeviceConnectionStatus failed: {exc}", file=sys.stderr)
            return False

    @pyqtSlot(str, result="QVariant")
    def resetDeviceToWaiting(self, host: str) -> dict[str, Any]:
        """Reset thiết bị disconnected về waiting để cho phép kết nối lại."""
        target_host = (host or "").strip()
        if not target_host:
            return {"ok": False, "message": "Host is empty.", "severity": "warning"}
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE t01_devices SET connection_status = ?, dev = 0 WHERE host = ?;",
                    (ConnectionStatus.WAITING.value, target_host),
                )
                conn.commit()
                if cursor.rowcount == 0:
                    return {"ok": False, "message": f"Device {target_host} not found.", "severity": "error"}
                return {"ok": True, "message": f"Device {target_host} reset to Waiting.", "severity": "success"}
        except Exception as e:
            return {"ok": False, "message": str(e), "severity": "error"}

    @pyqtSlot(str, int, result=bool)
    def updateDeviceDev(self, host: str, dev: int) -> bool:
        """Cập nhật cờ dev để đưa thiết bị vào hoặc ra khỏi luồng xử lý dev."""
        target_host = (host or "").strip()
        if not target_host:
            return False
        try:
            with self._connect() as conn:
                cursor = conn.execute("UPDATE t01_devices SET dev = ? WHERE host = ?;", (1 if dev else 0, target_host))
                conn.commit()
            if cursor.rowcount <= 0:
                return False
            return True
        except sqlite3.Error as exc:
            print(f"[db] updateDeviceDev failed: {exc}", file=sys.stderr)
            return False

    @pyqtSlot(str, int, str, result="QVariant")
    def setDeviceDevState(self, host: str, dev: int, status: str) -> dict[str, Any]:
        """Update development and connection flags together for one device."""
        target_host = (host or "").strip()
        dev_value = 1 if dev else 0
        action_name = (
            "Enable Development Mode"
            if dev_value
            else "Switch to Live Connection"
        )
        if not target_host:
            return {"ok": False, "severity": "warning", "message": f"{action_name} failed: host is empty."}

        try:
            status_value = connection_status(status).value
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE t01_devices SET dev = ?, connection_status = ? WHERE host = ?;",
                    (dev_value, status_value, target_host),
                )
                conn.commit()
            if cursor.rowcount <= 0:
                return {
                    "ok": False,
                    "severity": "error",
                    "message": f"{action_name} failed for {target_host}: device was not found.",
                }
            return {
                "ok": True,
                "severity": "success",
                "message": f"{action_name} applied for {target_host}.",
            }
        except (sqlite3.Error, ValueError) as exc:
            print(f"[db] setDeviceDevState failed: {exc}", file=sys.stderr)
            return {"ok": False, "severity": "error", "message": f"{action_name} failed for {target_host}: {exc}"}

    @pyqtSlot(str, str, str, str, str, str, result=bool)
    @pyqtSlot(str, str, str, str, str, str, str, str, str, result=bool)
    def updateDevice(
        self,
        host: str,
        device_name: str,
        method: str,
        port_text: str,
        username: str,
        password: str,
        os_name: str = "",
        role: str = "",
        device_type: str = "",
    ) -> bool:
        """Cập nhật thông tin kết nối và phân loại thiết bị trong DB."""
        target_host = (host or "").strip()
        if not target_host:
            return False
        try:
            port = int(port_text) if str(port_text).strip() else None
        except ValueError:
            return False
        if port is not None and not 1 <= port <= 65535:
            return False
        role = normalize_device_role(role, device_type) or "rou"
        device_type = device_type_for_role(role)
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT host FROM t01_devices WHERE host = ?;",
                    (target_host,),
                ).fetchone()
                if row is None:
                    return False

                cursor = conn.execute(
                    """
                    UPDATE t01_devices
                    SET device_name = ?, method = ?, portnumber = ?, username = ?, password = ?,
                        os = ?, role = ?, device_type = ?
                    WHERE host = ?;
                    """,
                    (
                        _clean_display_text(device_name) or None,
                        method or None,
                        port,
                        username or None,
                        password or None,
                        os_name or None,
                        role,
                        device_type,
                        target_host,
                    ),
                )
                conn.commit()
            if cursor.rowcount <= 0:
                return False
            return True
        except sqlite3.Error as exc:
            print(f"[db] updateDevice failed: {exc}", file=sys.stderr)
            return False

    @pyqtSlot(str, result="QVariant")
    def getDeviceByHost(self, host: str) -> dict[str, Any]:
        """Đọc chi tiết một thiết bị từ DB để trả về cho QML."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT host, device_name, method, portnumber, username, password, os, role, device_type, dev
                    FROM t01_devices
                    WHERE host = ?;
                    """,
                    ((host or "").strip(),),
                ).fetchone()
            if row is None:
                return {}
            return {
                "ip": row["host"],
                "name": _clean_display_text(row["device_name"]),
                "protocol": row["method"] or "SSH",
                "port": "" if row["portnumber"] is None else str(row["portnumber"]),
                "user": row["username"] or "",
                "pass": row["password"] or "",
                "os": row["os"] or "cisco_ios",
                "role": row["role"] or "",
                "type": device_type_for_role(row["role"]),
                "dev": row["dev"] if row["dev"] is not None else 0,
            }
        except sqlite3.Error as exc:
            print(f"[db] getDeviceByHost failed: {exc}", file=sys.stderr)
            return {}

    @pyqtSlot(result="QVariant")
    def getDevices(self) -> list[dict[str, Any]]:
        """Đọc danh sách thiết bị để hiển thị trên panel QML."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT host, device_name, connection_status, role, device_type, dev
                    FROM t01_devices
                    ORDER BY host COLLATE NOCASE;
                    """
                ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                status = connection_status(row["connection_status"]).value
                name = _clean_display_text(row["device_name"]) or row["host"]
                role = (row["role"] or "").strip().lower()
                device_type = device_type_for_role(role)
                out.append(
                    {
                        "name": name,
                        "ip": row["host"],
                        "status": status,
                        "connectionStatus": status,
                        "role": role,
                        "type": device_type,
                        "dev": int(row["dev"] or 0),
                    }
                )
            return _variant_list(out)
        except sqlite3.Error as exc:
            print(f"[db] getDevices failed: {exc}", file=sys.stderr)
            return []
