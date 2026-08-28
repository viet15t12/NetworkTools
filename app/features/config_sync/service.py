"""Decide when a committed running-config should update application state."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from features.devices.sync import sync_device_state
from features.switching.sync import sync_switch_state


RoleLookup = Callable[[str], str | None]
Synchronizer = Callable[[str, str, str, str | None], dict[str, Any]]
SwitchSynchronizer = Callable[[str, str, dict[str, str], str], dict[str, Any]]


class ConfigSyncService:
    """Gate the router sync pipeline by inventory role and Dulwich change state."""

    ROUTER_ROLE = "rou"

    def __init__(
        self,
        db_path: str | Path,
        role_lookup: RoleLookup,
        synchronizer: Synchronizer = sync_device_state,
        switch_synchronizer: SwitchSynchronizer = sync_switch_state,
    ) -> None:
        self.db_path = str(db_path)
        self._role_lookup = role_lookup
        self._synchronizer = synchronizer
        self._switch_synchronizer = switch_synchronizer

    def sync_committed_snapshot(
        self,
        host: str,
        running_config: str,
        interface_brief: str,
        commit_result: dict[str, Any],
        mode: str = "safe",
        switch_state: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Sync a changed router snapshot; return a structured decision/result."""
        normalized_host = (host or "").strip()
        base = {
            "host": normalized_host,
            "role": "",
            "attempted": False,
            "skipped": True,
            "changed": bool(commit_result.get("changed")),
            "commitId": str(commit_result.get("commitId") or ""),
        }
        has_interface_inventory = bool(str(interface_brief or "").strip())
        if (
            not bool(commit_result.get("changed"))
            and not has_interface_inventory
            and not switch_state
        ):
            return {
                **base,
                "ok": True,
                "reason": "unchanged",
                "message": "Running-config is unchanged; database sync was not needed.",
                "summary": {},
            }

        try:
            role = str(self._role_lookup(normalized_host) or "").strip().lower()
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "reason": "role-lookup-failed",
                "message": f"Could not verify device role: {exc}",
                "summary": {},
            }

        base["role"] = role
        if role in {"sw2", "sw3"}:
            if not switch_state:
                return {
                    **base,
                    "ok": True,
                    "reason": "not-router",
                    "message": "Config sync skipped because no switch operational state was collected.",
                    "summary": {},
                }
            try:
                switch_snapshot = dict(switch_state)
                if role == "sw3":
                    switch_snapshot["running_config"] = str(running_config or "")
                summary = self._switch_synchronizer(
                    self.db_path,
                    normalized_host,
                    switch_snapshot,
                    mode,
                )
                return {
                    **base,
                    "ok": True,
                    "attempted": True,
                    "skipped": False,
                    "reason": "synchronized",
                    "message": "Changed switch state was synchronized.",
                    "summary": dict(summary or {}),
                }
            except Exception as exc:
                return {
                    **base,
                    "ok": False,
                    "attempted": True,
                    "skipped": False,
                    "reason": "sync-failed",
                    "message": str(exc),
                    "summary": {},
                }
        if role != self.ROUTER_ROLE:
            return {
                **base,
                "ok": True,
                "reason": "not-router",
                "message": f"Config sync skipped because device role is {role or 'unknown'}, not rou.",
                "summary": {},
            }
        try:
            args = (
                self.db_path,
                normalized_host,
                str(running_config or ""),
                str(interface_brief or ""),
            )
            summary = (
                self._synchronizer(*args)
                if mode == "safe"
                else self._synchronizer(*args, mode=mode)
            )
            return {
                **base,
                "ok": True,
                "attempted": True,
                "skipped": False,
                "reason": "synchronized",
                "message": "Changed router configuration was synchronized.",
                "summary": dict(summary or {}),
            }
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "attempted": True,
                "skipped": False,
                "reason": "sync-failed",
                "message": str(exc),
                "summary": {},
            }

    def sync_manual_snapshot(
        self,
        host: str,
        running_config: str,
        interface_brief: str,
        commit_result: dict[str, Any],
        mode: str = "safe",
        switch_state: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run the same guarded pipeline even when the snapshot commit is unchanged."""
        forced_commit = dict(commit_result)
        forced_commit["changed"] = True
        result = self.sync_committed_snapshot(
            host, running_config, interface_brief, forced_commit, mode, switch_state
        )
        if result.get("ok") and result.get("reason") == "synchronized":
            result["reason"] = "manual-synchronized"
            result["message"] = "Manual Sync completed."
        return result

    def preview_manual_snapshot(
        self,
        host: str,
        running_config: str,
        interface_brief: str,
        commit_result: dict[str, Any],
        switch_state: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Parse and diff a manual snapshot without changing the database."""
        return self.sync_manual_snapshot(
            host,
            running_config,
            interface_brief,
            commit_result,
            mode="preview",
            switch_state=switch_state,
        )
