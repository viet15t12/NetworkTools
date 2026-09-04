"""Backward-compatible imports for Syslog domain models."""

from .domain.models import ListenerConfig, RawSyslogEvent, SEVERITY_NAMES, SyslogMessage

__all__ = ["ListenerConfig", "RawSyslogEvent", "SEVERITY_NAMES", "SyslogMessage"]
