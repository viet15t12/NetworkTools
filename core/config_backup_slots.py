"""Stable QML slots delegating versioned config reads to the feature service."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSlot


class ConfigBackupSlotsMixin:
    """Expose config history without owning Dulwich or legacy file logic."""

    @pyqtSlot(str, result="QVariant")
    def getLatestRunningConfig(self, host: str) -> dict[str, object]:
        """Read the latest committed configuration for one host."""
        return self._config_backup_service.read_latest(host)

    @pyqtSlot(str, result="QVariant")
    def getRunningConfigHistory(self, host: str) -> dict[str, object]:
        """Read the newest 100 configuration commits for one host."""
        return self._config_backup_service.list_history(host, 100)

    @pyqtSlot(str, str, result="QVariant")
    def getRunningConfigAtCommit(self, host: str, commit_id: str) -> dict[str, object]:
        """Read one reachable commit without checking it out."""
        return self._config_backup_service.read_commit(host, commit_id)

    @pyqtSlot(str, str, str, result="QVariant")
    def getRunningConfigDiff(
        self,
        host: str,
        base_commit_id: str,
        target_commit_id: str,
    ) -> dict[str, object]:
        """Return a unified diff for two Git history endpoints."""
        return self._config_backup_service.diff_commits(
            host,
            base_commit_id,
            target_commit_id,
        )
