"""OSPF routing persistence helpers."""

from .load import get_ospf_routing
from .save import save_ospf_routing

__all__ = ["get_ospf_routing", "save_ospf_routing"]
