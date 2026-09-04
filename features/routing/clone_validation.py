"""Clone validation contracts shared by service and UI adapters."""

from .clone_repository import CloneFailure, RoutingCloneRepository

__all__ = ["CloneFailure", "RoutingCloneRepository"]
