"""Backward-compatible imports for Cisco Syslog command generation."""

from .device_config.commands import build_cancel_commands, build_enable_commands

__all__ = ["build_cancel_commands", "build_enable_commands"]
