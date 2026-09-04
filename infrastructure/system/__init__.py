"""Operating-system adapters with no feature dependency."""

from .desktop_environment import (
    GLOBAL_MENU_PROBE_TIMEOUT_MS,
    GLOBAL_MENU_REGISTRAR,
    DesktopEnvironmentDetector,
    DesktopEnvironmentInfo,
)

__all__ = [
    "GLOBAL_MENU_PROBE_TIMEOUT_MS",
    "GLOBAL_MENU_REGISTRAR",
    "DesktopEnvironmentDetector",
    "DesktopEnvironmentInfo",
]
