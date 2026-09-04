"""Backward-compatible imports for the Qt Syslog settings adapter."""

from .qt.settings import SyslogSettings, _local_ipv4_addresses, _validate_ip

__all__ = ["SyslogSettings", "_local_ipv4_addresses", "_validate_ip"]
