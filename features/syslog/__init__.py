"""Public API for the isolated Syslog Server feature.

Imports are lazy so parser/command tests do not initialize Qt or database
services as a side effect.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .manager import SyslogManager
    from .settings import SyslogSettings

__all__ = ["SyslogManager", "SyslogSettings"]


def __getattr__(name: str) -> Any:
    if name == "SyslogManager":
        from .manager import SyslogManager

        return SyslogManager
    if name == "SyslogSettings":
        from .settings import SyslogSettings

        return SyslogSettings
    raise AttributeError(name)
