"""Stable DatabaseManager import surface for QML consumers."""

from .manager import DatabaseManager
from .unsupported_slots import UnsupportedSlotsMixin

__all__ = ["DatabaseManager", "UnsupportedSlotsMixin"]
