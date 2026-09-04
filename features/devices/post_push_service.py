"""Post-push persistence and device-state reconciliation."""

from __future__ import annotations

from typing import Any, Callable

from .save_config_service import SaveConfigService


class PostPushService:
    """Save, collect, back up, and synchronize one successful push.

    The caller is responsible for holding the per-host session lock. Keeping the
    whole sequence on one connector prevents another command from consuming the
    prompt or output that belongs to this operation.
    """

    def __init__(
        self,
        config_backup_service: Any,
        config_sync_service: Any,
        role_loader: Callable[[str], str] | None = None,
    ) -> None:
        self._backups = config_backup_service
        self._sync = config_sync_service
        self._role_loader = role_loader or (lambda _host: "")

    def reconcile(
        self,
        host: str,
        connector: Any,
        *,
        switch_state_keys: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist startup-config, collect one snapshot, then force-sync it."""
        host = str(host or "").strip()
        if not host:
            return self._failure("validate", "Post-push reconciliation failed: host is empty.")
        if connector is None:
            return self._failure("session", f"Post-push reconciliation failed for {host}: no active session.")
        try:
            save_output = SaveConfigService.copy_running_to_startup(connector)
        except Exception as exc:
            return self._failure(
                "save",
                f"Push completed, but copy running-config startup-config failed for {host}: {exc}",
            )

        snapshot = self._collect_snapshot(
            host,
            connector,
            switch_state_keys=switch_state_keys,
        )
        if not snapshot.get("ok"):
            return self._failure(
                "collect",
                str(snapshot.get("message") or f"Could not collect running-config from {host}."),
                save_output=save_output,
            )

        running_config = str(snapshot.get("running_config") or "")
        if not running_config.strip():
            return self._failure(
                "collect",
                f"The device returned an empty running-config after Push for {host}.",
                save_output=save_output,
            )

        try:
            backup = dict(self._backups.save_snapshot(host, running_config) or {})
        except Exception as exc:
            return self._failure(
                "backup",
                f"Post-push backup failed: {exc}",
                save_output=save_output,
            )
        if not bool(backup.get("ok")):
            return self._failure(
                "backup",
                str(backup.get("message") or "Post-push backup failed."),
                save_output=save_output,
                backup=backup,
            )

        if self._sync is None:
            return self._failure(
                "sync",
                "Post-push running-config sync service is unavailable.",
                save_output=save_output,
                backup=backup,
            )

        sync_args = (
            host,
            running_config,
            str(snapshot.get("interface_brief") or ""),
            backup,
        )
        switch_state = snapshot.get("switch_state")
        sync_kwargs = (
            {"switch_state": dict(switch_state)}
            if isinstance(switch_state, dict)
            else {}
        )
        try:
            sync = dict(
                self._sync.sync_manual_snapshot(
                    *sync_args,
                    mode="force_device_state",
                    **sync_kwargs,
                )
                or {}
            )
        except Exception as exc:
            return self._failure(
                "sync",
                f"Post-push database synchronization failed: {exc}",
                save_output=save_output,
                backup=backup,
            )
        if not bool(sync.get("ok")):
            return self._failure(
                "sync",
                str(sync.get("message") or "Post-push database synchronization failed."),
                save_output=save_output,
                backup=backup,
                sync=sync,
            )

        return {
            "ok": True,
            "stage": "complete",
            "message": (
                "Startup-config saved; running-config collected, backed up, "
                "and synchronized."
            ),
            "saveOutput": save_output,
            "backup": backup,
            "sync": sync,
            "snapshotUpdated": True,
        }

    def _collect_snapshot(
        self,
        host: str,
        connector: Any,
        *,
        switch_state_keys: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            snapshot = dict(connector.collect_running_config() or {})
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Could not collect running-config from {host}: {exc}",
            }
        if not bool(snapshot.get("ok")):
            detail = str(
                snapshot.get("message")
                or getattr(connector, "last_error", "")
                or "no output"
            )
            snapshot["message"] = f"Could not collect running-config from {host}: {detail}"
            return snapshot

        try:
            role = str(self._role_loader(host) or "").strip().lower()
        except Exception as exc:
            snapshot["switch_state_error"] = f"Could not resolve device role: {exc}"
            return snapshot
        if role not in {"sw2", "sw3"}:
            return snapshot
        if switch_state_keys is not None and not switch_state_keys:
            return snapshot
        try:
            switch_snapshot = dict(
                (
                    connector.collect_switch_state()
                    if switch_state_keys is None
                    else connector.collect_switch_state(switch_state_keys)
                )
                or {}
            )
        except Exception as exc:
            snapshot["switch_state_error"] = str(exc)
            return snapshot
        if switch_snapshot.get("ok"):
            snapshot["switch_state"] = dict(switch_snapshot.get("outputs") or {})
        else:
            snapshot["switch_state_error"] = str(
                switch_snapshot.get("message") or "Switch state collection failed."
            )
        return snapshot

    @staticmethod
    def _failure(
        stage: str,
        message: str,
        *,
        save_output: str = "",
        backup: dict[str, Any] | None = None,
        sync: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "stage": stage,
            "message": message,
            "saveOutput": save_output,
            "backup": backup or {},
            "sync": sync or {},
            "snapshotUpdated": bool(backup and backup.get("ok")),
        }


__all__ = ["PostPushService"]
