"""Backward-compatible import for the Syslog socket transport."""

from .transport.receiver import SyslogReceiver

__all__ = ["SyslogReceiver"]
