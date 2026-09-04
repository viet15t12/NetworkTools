"""Orchestrate PRI, Cisco timestamp, and Cisco message parsing."""

from __future__ import annotations

from ..domain.models import SyslogMessage
from .cisco import parse_cisco
from .pri import parse_pri
from .timestamp import parse_timestamp


def parse_message(data: bytes, source_ip: str, protocol: str) -> SyslogMessage:
    raw = data.decode("utf-8", errors="replace").replace("\x00", "").strip("\r\n ")
    pri = parse_pri(raw)
    timestamp = parse_timestamp(pri.remainder)
    cisco = parse_cisco(timestamp.remainder)

    severity = pri.severity if pri.severity is not None else 6
    message = timestamp.remainder or raw
    status = "partial" if pri.pri is not None or timestamp.device_time else "raw"
    cisco_facility = None
    cisco_subfacility = None
    mnemonic = None
    if cisco is not None:
        severity = cisco.severity
        cisco_facility = cisco.facility
        cisco_subfacility = cisco.subfacility
        mnemonic = cisco.mnemonic
        message = cisco.message or raw
        status = "parsed"

    return SyslogMessage(
        source_ip=source_ip,
        protocol=protocol,
        severity=severity,
        message=message,
        raw_message=raw,
        syslog_pri=pri.pri,
        syslog_facility=pri.facility,
        cisco_facility=cisco_facility,
        cisco_subfacility=cisco_subfacility,
        sequence_number=timestamp.sequence_number,
        device_time=timestamp.device_time,
        clock_unsynchronized=timestamp.clock_unsynchronized,
        mnemonic=mnemonic,
        parse_status=status,
    )


__all__ = ["parse_message"]
