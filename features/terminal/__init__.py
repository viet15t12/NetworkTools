"""App-managed external terminal feature and legacy embedded adapter."""

from .manager import InternalTerminalManager
from .managed_manager import ManagedTerminalManager
from .session import TerminalSession

__all__ = ["InternalTerminalManager", "ManagedTerminalManager", "TerminalSession"]
