"""Persistent connect-and-sync use case for one device."""

from __future__ import annotations

from typing import Any, Callable

from domain.status import ConnectionStatus


class DeviceConnectionService:
    def __init__(
        self,
        login_service: Any,
        device_service: Any,
        session_registry: Any,
        snapshot_committer: Callable[[str, dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]],
    ) -> None:
        self._login_service = login_service
        self._device_service = device_service
        self._sessions = session_registry
        self._commit_snapshot = snapshot_committer

    def connect_and_sync(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        if not host:
            return {"ok": False, "severity": "warning", "message": "Connect failed: host is empty."}
        device = self._login_service.load(host)
        if device is None:
            return {"ok": False, "severity": "error", "message": f"Connect failed for {host}: device was not found in database."}
        if self._login_service.is_dev_device(device):
            self._device_service.update_connection_status(
                host, ConnectionStatus.CONNECTED
            )
            return {
                "ok": True, "severity": "info",
                "message": f"{host} is a dev-test host; marked connected without a CLI session.",
            }
        opened = self._sessions.open(host)
        if not opened.get("ok"):
            self._device_service.update_connection_status(
                host, ConnectionStatus.DISCONNECTED
            )
            return opened

        def collect(connector: Any) -> dict[str, Any]:
            return connector.collect_running_config()

        collected = self._sessions.execute(host, collect, ensure_open=False)
        if not collected.get("ok"):
            self._device_service.update_connection_status(
                host, ConnectionStatus.DISCONNECTED
            )
            return collected
        snapshot = collected.get("value") or {}
        status_updated = self._device_service.update_connection_status(
            host, ConnectionStatus.CONNECTED
        )
        if not snapshot.get("ok"):
            return {
                "ok": True, "severity": "warning",
                "message": f"Connected {host}; running-config collection failed.",
            }
        role = str(device.get("role") or "").strip().lower()
        if role in {"sw2", "sw3"}:
            switch_result = self._sessions.execute(
                host,
                lambda connector: connector.collect_switch_state(),
                ensure_open=False,
            )
            switch_snapshot = switch_result.get("value") or {}
            if switch_result.get("ok") and switch_snapshot.get("ok"):
                snapshot["switch_state"] = dict(switch_snapshot.get("outputs") or {})
            else:
                snapshot["switch_state_error"] = str(
                    switch_snapshot.get("message")
                    or switch_result.get("message")
                    or "Switch state collection failed."
                )
        backup, sync = self._commit_snapshot(host, snapshot)
        if not backup.get("ok"):
            return {
                "ok": True, "severity": "warning",
                "message": f"Connected {host}; running-config backup failed.",
            }
        if not sync.get("ok", True):
            return {
                "ok": True, "severity": "warning", "sync": sync,
                "message": f"Connected {host}; backup succeeded, but DB sync failed: {sync.get('message')}.",
            }
        suffix = "" if status_updated else " Database status was not updated."
        return {
            "ok": True, "severity": "success", "sync": sync,
            "message": f"Connected {host}; running-config committed in backup/{host}/cfg.{suffix}",
        }
