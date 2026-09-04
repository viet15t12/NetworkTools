"""Backward-compatible import for the application batch writer."""

from .application.writer import SyslogWriter

__all__ = ["SyslogWriter"]
