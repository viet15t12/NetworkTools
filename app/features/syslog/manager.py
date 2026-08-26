"""Backward-compatible imports for the Qt Syslog adapter."""

from .qt.manager import SyslogManager, _variant_dict, _variant_list

__all__ = ["SyslogManager", "_variant_dict", "_variant_list"]
