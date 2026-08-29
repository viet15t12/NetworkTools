"""Public API for NetworkTools project package handling."""

from .crypto import Argon2Parameters, ENVELOPE_MAGIC, is_encrypted_package
from .errors import (
    InvalidWorkspacePackage,
    UnsupportedWorkspaceVersion,
    WorkspaceAuthenticationError,
    WorkspaceConflictError,
    WorkspaceLimitExceeded,
    WorkspacePackageError,
    WorkspacePasswordRequired,
)
from .package import (
    MANIFEST_NAME,
    PACKAGE_FORMAT,
    PACKAGE_VERSION,
    SNAPSHOT_INDEX_NAME,
    ContentEntry,
    PackageLimits,
    PackageFingerprint,
    WorkspaceManifest,
    WorkspacePackageCodec,
    WorkspaceSession,
    package_fingerprint,
)
from .locking import ProjectFileLock
from .service import RollbackResult, SaveResult, WorkspaceService
from .snapshot import SnapshotRecord, SnapshotService

__all__ = [
    "Argon2Parameters",
    "ContentEntry",
    "ENVELOPE_MAGIC",
    "InvalidWorkspacePackage",
    "MANIFEST_NAME",
    "PACKAGE_FORMAT",
    "PACKAGE_VERSION",
    "PackageLimits",
    "PackageFingerprint",
    "ProjectFileLock",
    "SNAPSHOT_INDEX_NAME",
    "SaveResult",
    "SnapshotRecord",
    "SnapshotService",
    "UnsupportedWorkspaceVersion",
    "WorkspaceAuthenticationError",
    "WorkspaceConflictError",
    "WorkspaceLimitExceeded",
    "WorkspaceManifest",
    "WorkspacePackageCodec",
    "WorkspacePackageError",
    "WorkspacePasswordRequired",
    "RollbackResult",
    "WorkspaceService",
    "WorkspaceSession",
    "is_encrypted_package",
    "package_fingerprint",
]
