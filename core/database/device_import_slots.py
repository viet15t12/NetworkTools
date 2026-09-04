"""QML slots grouped by the device import responsibility."""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

from PyQt6.QtCore import pyqtSlot

from .conversion import _clean_display_text
from features.devices.classification import device_type_for_role, normalize_device_role


class DeviceImportSlotsMixin:
    """Provide the stable QML contract for this responsibility."""

    def _file_url_to_path(self, value: str) -> Path:
        """Convert a local QML file URL or plain path into a filesystem path."""
        text = (value or "").strip()
        parsed = urlparse(text)
        if parsed.scheme == "file":
            path = unquote(parsed.path)
            if parsed.netloc:
                path = f"//{parsed.netloc}{path}"
            if sys.platform.startswith("win") and path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path[1:]
            return Path(path)
        return Path(text)

    def _normalize_import_key(self, key: Any) -> str:
        """Map supported spreadsheet/JSON column aliases to canonical keys."""
        text = str(key or "").strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "ip": "host",
            "hostname": "host",
            "device_name": "name",
            "protocol": "method",
            "port": "portnumber",
            "port_number": "portnumber",
            "user": "username",
            "pass": "password",
            "device_type": "type",
            "netmiko_type": "os",
        }
        return aliases.get(text, text)

    def _normalize_import_row(self, raw: Mapping[str, Any], line_number: int) -> dict[str, Any]:
        """Chuẩn hóa một dòng import thiết bị trước khi ghi vào DB."""
        row = {self._normalize_import_key(key): value for key, value in raw.items()}
        method = str(row.get("method") or "SSH").strip().upper()
        default_port = 23 if method == "TELNET" else 830 if method == "NETCONF" else 443 if method == "RESTCONF" else 22
        role = normalize_device_role(row.get("role"), row.get("type") or row.get("device_type")) or "rou"
        device_type = device_type_for_role(role)
        return {
            "lineNumber": line_number,
            "host": str(row.get("host") or "").strip(),
            "name": _clean_display_text(row.get("name")),
            "method": method,
            "port": self._int_or_none(row.get("portnumber")) or default_port,
            "username": str(row.get("username") or "").strip(),
            "password": str(row.get("password") or "").strip(),
            "os": str(row.get("os") or "cisco_ios").strip() or "cisco_ios",
            "role": role,
            "type": device_type,
        }

    def _read_json_import_rows(self, path: Path) -> list[dict[str, Any]]:
        """Đọc danh sách thiết bị từ file JSON import."""
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            for key in ("devices", "rows", "items"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        rows = self._as_list(data)
        return [self._normalize_import_row(self._as_dict(row), index + 1) for index, row in enumerate(rows)]

    def _xlsx_cell_text(self, cell: ElementTree.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
        """Decode one XLSX XML cell, including shared-string references."""
        cell_type = cell.attrib.get("t", "")
        value = cell.find("x:v", ns)
        inline = cell.find("x:is/x:t", ns)
        text = inline.text if inline is not None else value.text if value is not None else ""
        if cell_type == "s":
            index = self._int_or_none(text)
            if index is not None and 0 <= index < len(shared_strings):
                return shared_strings[index]
        return text or ""

    def _xlsx_column_index(self, cell_ref: str) -> int:
        """Convert an Excel column reference such as C12 to a zero-based index."""
        letters = "".join(ch for ch in (cell_ref or "") if ch.isalpha()).upper()
        index = 0
        for ch in letters:
            index = index * 26 + (ord(ch) - ord("A") + 1)
        return max(index - 1, 0)

    def _read_xlsx_import_rows(self, path: Path) -> list[dict[str, Any]]:
        """Đọc danh sách thiết bị từ file Excel import."""
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(path) as workbook:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in workbook.namelist():
                root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
                for item in root.findall("x:si", ns):
                    shared_strings.append("".join(node.text or "" for node in item.findall(".//x:t", ns)))

            sheet_name = "xl/worksheets/sheet1.xml"
            root = ElementTree.fromstring(workbook.read(sheet_name))
            table: list[list[str]] = []
            for row in root.findall(".//x:sheetData/x:row", ns):
                values: list[str] = []
                for cell in row.findall("x:c", ns):
                    column = self._xlsx_column_index(cell.attrib.get("r", ""))
                    while len(values) <= column:
                        values.append("")
                    values[column] = self._xlsx_cell_text(cell, shared_strings, ns).strip()
                if any(values):
                    table.append(values)

        if not table:
            return []
        headers = [self._normalize_import_key(value) for value in table[0]]
        rows: list[dict[str, Any]] = []
        for index, values in enumerate(table[1:], start=2):
            raw = {headers[col]: values[col] if col < len(values) else "" for col in range(len(headers))}
            rows.append(self._normalize_import_row(raw, index))
        return rows

    def _import_devices_from_path(self, path: Path) -> dict[str, Any]:
        """Import thiết bị từ file và ghi các bản ghi mới vào t01_devices."""
        if not path.exists():
            return {"ok": False, "message": f"File not found: {path}", "added": 0, "skipped": 0}

        suffix = path.suffix.lower()
        if suffix == ".json":
            rows = self._read_json_import_rows(path)
        elif suffix == ".xlsx":
            rows = self._read_xlsx_import_rows(path)
        else:
            return {"ok": False, "message": "Only .xlsx and .json imports are supported.", "added": 0, "skipped": 0}

        if not rows:
            return {"ok": False, "message": "No device rows found in import file.", "added": 0, "skipped": 0}

        added = 0
        skipped = 0
        with self._connect() as conn:
            for row in rows:
                if not row["host"]:
                    skipped += 1
                    continue
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO t01_devices
                        (host, device_name, method, portnumber, username, password, os, role, connection_status, dev, device_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, ?);
                    """,
                    (
                        row["host"],
                        _clean_display_text(row["name"]) or None,
                        row["method"] or None,
                        row["port"],
                        row["username"] or None,
                        row["password"] or None,
                        row["os"] or None,
                        row["role"] or None,
                        row["type"] or "unknown",
                    ),
                )
                if cursor.rowcount:
                    added += 1
                else:
                    skipped += 1
            conn.commit()

        folders_ok = True
        message = f"Imported {added}/{len(rows)} devices. Skipped: {skipped}."
        if added > 0 and not folders_ok:
            message += " Backup folder creation failed."
        return {"ok": added > 0, "message": message, "added": added, "skipped": skipped, "foldersOk": folders_ok}

    @pyqtSlot(str, result="QVariant")
    def importDevicesFromFile(self, file_url: str) -> dict[str, Any]:
        """Nhận file từ QML và import danh sách thiết bị vào DB."""
        try:
            return self._import_devices_from_path(self._file_url_to_path(file_url))
        except Exception as exc:
            print(f"[db] importDevicesFromFile failed: {exc}", file=sys.stderr)
            return {"ok": False, "message": str(exc), "added": 0, "skipped": 0}

    @pyqtSlot(str, result="QVariant")
    def saveDeviceImportSample(self, file_url: str) -> dict[str, Any]:
        """Copy the bundled device-import workbook to a user-selected path."""
        try:
            source = self.app_dir / "template" / "EXdevices.xlsx"
            if not source.exists():
                return {"ok": False, "message": f"Sample file not found: {source}"}

            target = self._file_url_to_path(file_url)
            if target.suffix.lower() != ".xlsx":
                target = target.with_suffix(".xlsx")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            return {"ok": True, "message": f"Saved sample Excel file:\n{target}"}
        except Exception as exc:
            print(f"[db] saveDeviceImportSample failed: {exc}", file=sys.stderr)
            return {"ok": False, "message": str(exc)}
