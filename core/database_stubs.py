"""Compatibility import for the relocated unsupported slot mixin."""

from .database.unsupported_slots import UnsupportedSlotsMixin


class StubSlotsMixin(UnsupportedSlotsMixin):
    """Deprecated alias; use ``core.database.UnsupportedSlotsMixin`` instead."""

    pass


__all__ = ["StubSlotsMixin"]
