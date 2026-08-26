"""Dependency-free Excel export for the Syslog rows visible in QML."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile
from urllib.parse import unquote, urlparse
from xml.sax.saxutils import escape
import zipfile


_HEADERS = (
    "Received at", "Device time", "Host", "Source IP", "Protocol",
    "Severity", "Facility", "Mnemonic", "Message", "Raw message",
    "Sequence", "Parse status",
)
_SEVERITY_NAMES = (
    "Emergency", "Alert", "Critical", "Error",
    "Warning", "Notice", "Informational", "Debug",
)


def file_url_to_path(value: str) -> Path:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        if parsed.netloc:
            path = f"//{parsed.netloc}{path}"
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return Path(path)
    return Path(text)


def _clean_text(value: object) -> str:
    text = str(value if value is not None else "")
    text = "".join(
        char for char in text
        if char in "\t\n\r" or ord(char) >= 0x20
    )
    return text[:32767]


def _inline_cell(reference: str, value: object, style: int = 5) -> str:
    text = escape(_clean_text(value))
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr">'
        f"<is><t{preserve}>{text}</t></is></c>"
    )


def _number_cell(reference: str, value: int | float | str, style: int = 5) -> str:
    return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'


def _excel_datetime(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    epoch = datetime(1899, 12, 30)
    return (parsed - epoch).total_seconds() / 86400


def _date_or_text_cell(reference: str, value: object) -> str:
    serial = _excel_datetime(value)
    if serial is None:
        return _inline_cell(reference, value)
    return _number_cell(reference, f"{serial:.12f}", 6)


def _column_name(index: int) -> str:
    result = ""
    value = index
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _severity_value(row: Mapping[str, object]) -> tuple[int, str]:
    try:
        severity = int(row.get("severity", 6) or 0)
    except (TypeError, ValueError):
        severity = 6
    severity = max(0, min(severity, 7))
    return severity, f"{severity} · {_SEVERITY_NAMES[severity]}"


def _severity_style(severity: int) -> int:
    if severity <= 3:
        return 8
    if severity == 4:
        return 9
    if severity == 5:
        return 10
    return 11


def _filters_summary(filters: Mapping[str, object]) -> str:
    parts: list[str] = []
    labels = (
        ("host", "Host"), ("from_time", "From"), ("to_time", "To"),
        ("per_host", "Latest/host"), ("facility", "Facility"),
        ("mnemonic", "Mnemonic"), ("smart_query", "Smart query"),
    )
    for key, label in labels:
        value = filters.get(key)
        if value not in (None, "", 0, [], ()):
            parts.append(f"{label}: {value}")
    severities = filters.get("severities") or []
    if severities:
        parts.append("Severity: " + ", ".join(str(value) for value in severities))
    protocols = filters.get("protocols") or []
    if protocols:
        parts.append("Protocol: " + ", ".join(str(value).upper() for value in protocols))
    search = str(filters.get("search") or "").strip()
    if search and not str(filters.get("smart_query") or "").strip():
        parts.append(f"Search: {search}")
    return " | ".join(parts) if parts else "No filters"


def _sheet_xml(rows: Sequence[Mapping[str, object]], filters: Mapping[str, object]) -> str:
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sheet_rows: list[str] = []
    sheet_rows.append(
        '<row r="1" ht="28" customHeight="1">'
        + _inline_cell("A1", "NetworkTools Syslog Export", 1) + "</row>"
    )
    sheet_rows.append(
        '<row r="2">' + _inline_cell("A2", "Exported at (UTC)", 2)
        + _inline_cell("B2", exported_at, 3) + "</row>"
    )
    sheet_rows.append(
        '<row r="3">' + _inline_cell("A3", "Displayed rows", 2)
        + _number_cell("B3", len(rows), 3) + "</row>"
    )
    sheet_rows.append(
        '<row r="4" ht="30" customHeight="1">'
        + _inline_cell("A4", "Active filters", 2)
        + _inline_cell("B4", _filters_summary(filters), 7) + "</row>"
    )
    header_cells = "".join(
        _inline_cell(f"{_column_name(index)}6", header, 4)
        for index, header in enumerate(_HEADERS, start=1)
    )
    sheet_rows.append(f'<row r="6" ht="24" customHeight="1">{header_cells}</row>')

    for row_number, row in enumerate(rows, start=7):
        severity, severity_label = _severity_value(row)
        sequence = row.get("sequence_number")
        try:
            sequence_value: int | str = int(sequence) if sequence is not None else ""
            if sequence_value != "" and sequence_value < 0:
                sequence_value = ""
        except (TypeError, ValueError):
            sequence_value = ""
        values = (
            row.get("received_at", ""),
            row.get("device_time", ""),
            row.get("device_host", ""),
            row.get("source_ip", ""),
            str(row.get("protocol") or "").upper(),
            severity_label,
            row.get("cisco_facility") or row.get("facility") or "",
            row.get("mnemonic", ""),
            row.get("message", ""),
            row.get("raw_message", ""),
            sequence_value,
            row.get("parse_status", ""),
        )
        cells: list[str] = []
        for column_index, value in enumerate(values, start=1):
            reference = f"{_column_name(column_index)}{row_number}"
            if column_index in {1, 2}:
                cells.append(_date_or_text_cell(reference, value))
            elif column_index == 6:
                cells.append(_inline_cell(reference, value, _severity_style(severity)))
            elif column_index in {9, 10}:
                cells.append(_inline_cell(reference, value, 7))
            elif column_index == 11 and value != "":
                cells.append(_number_cell(reference, int(value), 5))
            else:
                cells.append(_inline_cell(reference, value, 5))
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    last_row = max(6, len(rows) + 6)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetPr><pageSetUpPr fitToPage="1" autoPageBreaks="0"/></sheetPr>
  <dimension ref="A1:L{last_row}"/>
  <sheetViews><sheetView workbookViewId="0" showGridLines="0">
    <pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/>
    <selection pane="bottomLeft" activeCell="A7" sqref="A7"/>
  </sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>
    <col min="1" max="2" width="24" customWidth="1"/><col min="3" max="4" width="18" customWidth="1"/>
    <col min="5" max="5" width="11" customWidth="1"/><col min="6" max="6" width="18" customWidth="1"/>
    <col min="7" max="8" width="18" customWidth="1"/><col min="9" max="10" width="52" customWidth="1"/>
    <col min="11" max="11" width="12" customWidth="1"/><col min="12" max="12" width="16" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
  <mergeCells count="3"><mergeCell ref="A1:L1"/><mergeCell ref="B2:L2"/><mergeCell ref="B4:L4"/></mergeCells>
  <autoFilter ref="A6:L{last_row}"/>
  <pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <printOptions horizontalCentered="1"/>
  <pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>'''


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm:ss.000"/></numFmts>
  <fonts count="5">
    <font><sz val="10"/><name val="Aptos"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="16"/><name val="Aptos Display"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font>
    <font><b/><color rgb="FF1F2937"/><sz val="10"/><name val="Aptos"/></font>
    <font><color rgb="FF4B5563"/><sz val="10"/><name val="Aptos"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF2457A7"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEFF6FF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF7E6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFECEC"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2"><border/><border><bottom style="thin"><color rgb="FFD7DEE8"/></bottom></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="12">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top"/></xf>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment vertical="top"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="4" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def export_logs_xlsx(
    target: Path,
    rows: Sequence[Mapping[str, object]],
    filters: Mapping[str, object] | None = None,
) -> Path:
    """Write visible Syslog rows to a formatted, filterable XLSX workbook."""

    destination = Path(target)
    if destination.suffix.lower() != ".xlsx":
        destination = destination.with_suffix(".xlsx")
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_rows = [dict(row) for row in rows]
    normalized_filters = dict(filters or {})

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="Syslog" sheetId="1" r:id="rId1"/></sheets>
  <calcPr calcId="191029"/>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>NetworkTools Syslog Export</dc:title><dc:creator>NetworkTools</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
</cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>NetworkTools</Application><AppVersion>1.0</AppVersion>
</Properties>'''

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".syslog-export-", suffix=".xlsx", dir=destination.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", root_rels)
            archive.writestr("docProps/core.xml", core)
            archive.writestr("docProps/app.xml", app)
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            archive.writestr("xl/styles.xml", _styles_xml())
            archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(normalized_rows, normalized_filters))
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


__all__ = ["export_logs_xlsx", "file_url_to_path"]
