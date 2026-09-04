"""Backward-compatible schema imports."""

from .persistence.schema import SYSLOG_SCHEMA_SQL, ensure_schema

__all__ = ["SYSLOG_SCHEMA_SQL", "ensure_schema"]
