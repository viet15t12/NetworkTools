"""Coordinate router-interface preview, transport, and state updates."""

from __future__ import annotations

from typing import Any

from core.view_push import BaseViewPushController

from .collector import collect_interface_tasks
from .commands import (
    redact_interface_commands,
    redact_interface_output,
    render_interface_commands,
)
from .push_state import mark_interface_task_applied
from .worker import apply_interface_commands


class InterfaceViewPushController(BaseViewPushController):
    """App-facing View & Push controller for Cisco IOS router interfaces."""

    module_label = "Router Interface"

    def _check_target(self, host: str, module_name: str) -> None:
        module = (module_name or "all").strip().lower()
        if module not in {"all", "interface"}:
            raise ValueError(f"Unsupported router-interface module: {module_name}")
        context = self.db._routing_device_context(host)
        if context["template_folder"] != "cisco_ios":
            raise ValueError(
                "Router Interface View & Push currently supports Cisco IOS only, "
                f"not {context['platform']}"
            )
        if str(context.get("method") or "SSH").upper() == "RESTCONF":
            raise ValueError("Router Interface RESTCONF push is not integrated yet")

    def collect_pending_tasks(
        self, host: str, module_name: str = "all"
    ) -> list[dict[str, Any]]:
        self._check_target(host, module_name)
        tasks = collect_interface_tasks(self.db, host)
        for task in tasks:
            task["commands"] = render_interface_commands(task)
        return [task for task in tasks if task["commands"]]

    def render_task_preview(
        self, task: dict[str, Any], module_name: str = "all"
    ) -> list[str]:
        name = task["interface"]["interface_name"]
        return [
            f"# {task['target']['ip']} / ROUTER INTERFACE / {name}",
            *redact_interface_commands(task["commands"]),
        ]

    def preview(self, host: str, module_name: str = "all") -> dict[str, Any]:
        """Return redacted commands and non-secret task summaries to QML."""
        result = super().preview(host, module_name)
        if result.get("ok"):
            result["tasks"] = [
                {
                    "target": task.get("target", {}),
                    "interface": task.get("interface", {}).get("interface_name", ""),
                    "action": task.get("action", "setup"),
                }
                for task in result.get("tasks", [])
            ]
        return result

    def push_tasks(
        self, host: str, module_name: str, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        provider = self._session_provider_for_host(host)
        if provider is None:
            raise ValueError("Router Interface RESTCONF push is not implemented")
        connector = provider(host)
        if connector is None:
            raise RuntimeError(f"Could not open a device session for {host}")

        report: list[dict[str, Any]] = []
        commands = [
            command
            for task in tasks
            for command in list(task.get("commands") or [])
        ]
        try:
            output = apply_interface_commands(connector, commands)
            for task in tasks:
                name = str(task["interface"]["interface_name"])
                mark_interface_task_applied(self.db, task)
                report.append(
                    {
                        "ip": host,
                        "interface": name,
                        "status": "SUCCESS",
                        "log": redact_interface_output(output),
                        "db_updated": True,
                    }
                )
        except Exception as exc:
            for task in tasks:
                name = str(task["interface"]["interface_name"])
                report.append(
                    {
                        "ip": host,
                        "interface": name,
                        "status": "FAIL",
                        "log": redact_interface_output(str(exc)),
                        "db_updated": False,
                    }
                )

        ok = bool(report) and all(item["status"] == "SUCCESS" for item in report)
        detail = next(
            (item["log"] for item in report if item["status"] != "SUCCESS"), ""
        )
        return {
            "ok": ok,
            "message": (
                "Router Interface push completed."
                if ok
                else f"Router Interface push stopped: {detail}"
            ),
            "report": report,
        }


__all__ = ["InterfaceViewPushController"]
