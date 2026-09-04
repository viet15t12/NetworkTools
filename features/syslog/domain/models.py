"""Pure Python data objects shared by the Syslog layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


SEVERITY_NAMES = (
    "emergency", "alert", "critical", "error",
    "warning", "notice", "informational", "debug",
)


@dataclass(slots=True, frozen=True)
class RawSyslogEvent:
    data: bytes
    source_ip: str
    protocol: str


@dataclass(slots=True)
class SyslogMessage:
    source_ip: str
    severity: int
    message: str
    raw_message: str
    protocol: str
    device_host: str = ""
    received_at: str = ""
    device_time: str | None = None
    sequence_number: int | None = None
    clock_unsynchronized: bool = False
    syslog_pri: int | None = None
    syslog_facility: int | None = None
    cisco_facility: str | None = None
    cisco_subfacility: str | None = None
    mnemonic: str | None = None
    parse_status: str = "parsed"
    # Compatibility field used by existing QML and integrations. New code must
    # use the explicit syslog_facility/cisco_facility fields instead.
    facility: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= int(self.severity) <= 7:
            self.severity = 6
        if not self.received_at:
            self.received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.protocol = self.protocol.lower()
        if self.syslog_pri is not None and 0 <= int(self.syslog_pri) <= 191:
            if self.syslog_facility is None:
                self.syslog_facility = int(self.syslog_pri) // 8
        if self.cisco_facility is None and self.facility and not self.facility.isdigit():
            self.cisco_facility = self.facility
        if self.syslog_facility is None and self.facility and self.facility.isdigit():
            legacy_facility = int(self.facility)
            if 0 <= legacy_facility <= 23:
                self.syslog_facility = legacy_facility
        if self.facility is None:
            if self.cisco_facility:
                self.facility = self.cisco_facility
            elif self.syslog_facility is not None:
                self.facility = str(self.syslog_facility)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["clock_unsynchronized"] = bool(self.clock_unsynchronized)
        row["severity_name"] = SEVERITY_NAMES[self.severity]
        return row


@dataclass(slots=True, frozen=True)
class ListenerConfig:
    bind_ip: str
    advertised_ip: str
    port: int
    protocol: str
    max_message_bytes: int = 16 * 1024
    max_tcp_clients: int = 64
