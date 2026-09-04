"""Unsupported QML slots retained only when no implemented feature owns them."""

from __future__ import annotations

class UnsupportedSlotsMixin:
    """Return predictable results for the remaining unsupported interface slots."""

    def _unsupported_write(self, operation: str) -> bool:
        """Report an unsupported mutation without changing application data."""
        logger = getattr(self, "_log", None)
        if callable(logger):
            logger("WARNING", f"{operation} is not implemented; no data was changed.", "SYSTEM", "db")
        return False
