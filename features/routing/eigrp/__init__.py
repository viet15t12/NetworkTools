"""EIGRP routing persistence helpers."""

from .load import get_eigrp_routing
from .save import save_eigrp_routing

__all__ = ["get_eigrp_routing", "save_eigrp_routing"]
