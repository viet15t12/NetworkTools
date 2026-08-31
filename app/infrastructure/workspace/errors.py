"""Typed failures raised by the CAMS workspace package layer."""

from __future__ import annotations


class WorkspacePackageError(Exception):
    """Base class for failures safe to translate at the UI boundary."""


class InvalidWorkspacePackage(WorkspacePackageError):
    """The package is malformed, unsafe, or fails an integrity check."""


class UnsupportedWorkspaceVersion(WorkspacePackageError):
    """The package or encryption envelope uses an unsupported version."""


class WorkspaceLimitExceeded(InvalidWorkspacePackage):
    """A configured archive resource limit was exceeded."""


class WorkspacePasswordRequired(WorkspacePackageError):
    """An encrypted project was opened without a password."""


class WorkspaceAuthenticationError(WorkspacePackageError):
    """The password is wrong or the authenticated package was modified."""


class WorkspaceConflictError(WorkspacePackageError):
    """The destination changed externally while a replacement was prepared."""

    def __init__(self, message: str, temporary_path: str = "") -> None:
        super().__init__(message)
        self.temporary_path = temporary_path


__all__ = [
    "InvalidWorkspacePackage",
    "UnsupportedWorkspaceVersion",
    "WorkspaceAuthenticationError",
    "WorkspaceConflictError",
    "WorkspaceLimitExceeded",
    "WorkspacePackageError",
    "WorkspacePasswordRequired",
]
