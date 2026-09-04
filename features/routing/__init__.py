"""Routing persistence services used by the PyQt bridge."""

from .static_route import get_static_routing, save_static_routing, save_static_routes
from .static_default import get_default_routes, save_default_routes
from .ospf import get_ospf_routing, save_ospf_routing
from .eigrp import get_eigrp_routing, save_eigrp_routing

__all__ = [
    "get_static_routing",
    "save_static_routing",
    "save_static_routes",
    "get_default_routes",
    "save_default_routes",
    "get_ospf_routing",
    "save_ospf_routing",
    "get_eigrp_routing",
    "save_eigrp_routing",
]
