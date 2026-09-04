"""Backward-compatible imports for Cisco Syslog configuration."""

from .device_config.service import SyslogConfigurator
from .device_config.verifier import contains_cli_error as _contains_cli_error

__all__ = ["SyslogConfigurator", "_contains_cli_error"]
