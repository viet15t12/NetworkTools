"""Composition helper for the database facade's View & Push runtime."""

from __future__ import annotations

from typing import Any

from core.app_paths import APP_DIR
from core.tasks import AsyncTaskCoordinator
from core.view_push import ViewPushControllerFactory
from core.view_push_batch import ViewPushBatchService
from features.config_backup import ConfigBackupService
from features.devices import DeviceRepository, PostPushService


def initialize_view_push_runtime(
    owner: Any,
    config_backup_service: Any,
    config_sync_service: Any,
    task_coordinator: Any,
    session_registry: Any,
) -> None:
    """Attach Push, post-Push, backup, and background-task services."""
    owner._background_tasks = {}
    owner._task_coordinator = task_coordinator or AsyncTaskCoordinator(owner)
    owner._config_backup_service = config_backup_service or ConfigBackupService(
        APP_DIR / "backup"
    )
    owner._config_sync_service = config_sync_service
    owner._post_push_service = PostPushService(
        owner._config_backup_service,
        owner._config_sync_service,
        lambda host: DeviceRepository(owner.db_path).get_role(host),
    )
    owner._view_push = ViewPushControllerFactory(owner, session_registry)
    owner._view_push_batch = ViewPushBatchService(
        owner._view_push, max_concurrent_hosts=5
    )


__all__ = ["initialize_view_push_runtime"]
