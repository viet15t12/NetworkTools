"""Public named-result running-config parser API."""

from .sync.parser import (
    ParsedRouterConfig,
    parse_running_config_sections,
    parse_static_route_line,
)

__all__ = [
    "ParsedRouterConfig",
    "parse_running_config_sections",
    "parse_static_route_line",
]
