"""Persist a device's active configuration through an app-owned CLI session."""

from __future__ import annotations

from typing import Any


class SaveConfigService:
    """Save running configuration without exposing credentials or shell commands."""

    @staticmethod
    def _command_rejected(output: str) -> bool:
        lowered = str(output or "").lower()
        return "% invalid input" in lowered or "invalid input detected" in lowered

    def __init__(self, session_registry: Any) -> None:
        self._session_registry = session_registry

    @staticmethod
    def copy_running_to_startup(connector: Any) -> str:
        """Run the explicit post-push copy command on an owned connector."""
        connection = getattr(connector, "connection", None)
        if connection is None:
            raise RuntimeError("Device connection is not available")
        save_config = getattr(connection, "save_config", None)
        if not callable(save_config):
            raise RuntimeError("The active device driver does not support saving configuration")
        try:
            output = str(
                save_config(
                    cmd="copy running-config startup-config",
                    confirm=True,
                )
                or ""
            )
        except (TypeError, NotImplementedError) as exc:
            raise RuntimeError(
                "The active device driver cannot run copy running-config startup-config"
            ) from exc
        if SaveConfigService._command_rejected(output):
            raise RuntimeError("The device rejected copy running-config startup-config")
        return output

    @staticmethod
    def _save(connector: Any) -> str:
        connection = getattr(connector, "connection", None)
        if connection is None:
            raise RuntimeError("Device connection is not available")

        save_config = getattr(connection, "save_config", None)
        if not callable(save_config):
            raise RuntimeError("The active device driver does not support saving configuration")

        output = str(save_config() or "")
        if SaveConfigService._command_rejected(output):
            # Cisco IOS normally uses ``write mem``, but several virtual/lab
            # images only accept the explicit copy command and prompt for the
            # destination filename.  Retry through the same driver/session.
            try:
                fallback = str(
                    save_config(
                        cmd="copy running-config startup-config",
                        confirm=True,
                    )
                    or ""
                )
            except (TypeError, NotImplementedError) as exc:
                raise RuntimeError(
                    "The device rejected the save configuration command"
                ) from exc
            if SaveConfigService._command_rejected(fallback):
                raise RuntimeError(
                    "The device rejected both supported save configuration commands"
                )
            output = fallback
        return output

    def save(self, host: str) -> dict[str, Any]:
        """Save through an already-open session; never open a surprise connection."""
        host = str(host or "").strip()
        if not host:
            return {
                "ok": False,
                "severity": "warning",
                "message": "Save configuration failed: host is empty.",
            }

        result = self._session_registry.execute(
            host,
            self._save,
            ensure_open=False,
        )
        if not bool(result.get("ok")):
            return {
                **result,
                "message": str(result.get("message") or f"Save configuration failed for {host}."),
            }
        return {
            "ok": True,
            "severity": "success",
            "message": f"Running configuration saved to startup configuration on {host}.",
            "output": str(result.get("value") or ""),
        }
