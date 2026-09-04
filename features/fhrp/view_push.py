"""View & Push controller for FHRP."""

from __future__ import annotations

from typing import Any

from core.view_push import BaseViewPushController, _variant_list

from .collector import collect_fhrp_tasks
from .commands import redact_fhrp_commands, render_fhrp_commands
from .push_state import apply_fhrp_success
from .verification import verify_fhrp_task
from .worker import push_fhrp_tasks


class FhrpViewPushController(BaseViewPushController):
    """Preview and push all pending FHRP members for one host."""

    module_label = "FHRP"

    def collect_pending_tasks(
        self, host: str, module_name: str = "all"
    ) -> list[dict[str, Any]]:
        tasks = collect_fhrp_tasks(self.db, self._clean_host(host))
        protocol = str(module_name or "all").strip().lower()
        if protocol in {"hsrp", "vrrp", "glbp"}:
            return [task for task in tasks if task["sub_type"] == protocol]
        return tasks

    def render_task_preview(
        self, task: dict[str, Any], module_name: str = "all"
    ) -> list[str]:
        host = task["target"]["ip"]
        context = self.db._routing_device_context(host)
        commands = render_fhrp_commands(task, context["template_folder"])
        return [
            f"# {host} / {task['sub_type'].upper()} / {task['action'].upper()}",
            *redact_fhrp_commands(commands),
        ]

    def push_tasks(
        self, host: str, module_name: str, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        context = self.db._routing_device_context(host)
        if context["template_folder"] != "cisco_ios":
            return {
                "ok": False,
                "message": "FHRP push currently supports Cisco IOS only.",
                "report": [],
            }
        provider = self._session_provider_for_host(host)
        if provider is None:
            return {
                "ok": False,
                "message": "FHRP RESTCONF push is not integrated.",
                "report": [],
            }
        # The foreground transaction only sends configuration and checks CLI
        # rejection. Operational show commands and DB advancement run later in
        # verify_after_push(), outside the user's Push dialog.
        reports = push_fhrp_tasks(
            tasks,
            context["template_folder"],
            provider,
            verify=False,
        )
        ok = bool(reports) and all(row["status"] == "SUCCESS" for row in reports)
        detail = next(
            (row["log"] for row in reports if row["status"] != "SUCCESS"),
            "",
        )
        return {
            "ok": ok,
            "message": (
                "FHRP push completed."
                if ok
                else f"FHRP push finished with errors: {detail}"
            ),
            "report": _variant_list(
                [{key: value for key, value in row.items() if key != "task"} for row in reports]
            ),
        }

    def post_push_context(
        self, tasks: list[dict[str, Any]], result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Retain only fields needed for safe deferred verification and DB update."""
        context: list[dict[str, Any]] = []
        for task in tasks:
            config = dict(task.get("config") or {})
            context.append(
                {
                    "target": {"ip": str(task.get("target", {}).get("ip") or "")},
                    "action": str(task.get("action") or "setup"),
                    "sub_type": str(task.get("sub_type") or ""),
                    "config": {
                        "member_id": config.get("member_id"),
                        "fhrp_id": config.get("fhrp_id"),
                        "interface_name": config.get("interface_name"),
                        "protocol": config.get("protocol"),
                        "group_number": config.get("group_number"),
                        "virtual_ip": config.get("virtual_ip"),
                    },
                }
            )
        return context

    def verify_after_push(
        self,
        host: str,
        module_name: str,
        connector: Any,
        context: Any,
    ) -> dict[str, Any]:
        """Verify FHRP state and advance pending rows during background sync."""
        tasks = [dict(task) for task in context] if isinstance(context, list) else []
        if not tasks:
            return {
                "ok": True,
                "skipped": True,
                "message": "No deferred FHRP verification was required.",
            }
        connection = getattr(connector, "connection", connector)
        report: list[dict[str, Any]] = []
        show_cache: dict[str, str] = {}
        for task in tasks:
            try:
                detail = verify_fhrp_task(
                    connection,
                    task,
                    show_cache=show_cache,
                )
                apply_fhrp_success(self.db, task)
                report.append({"ok": True, "message": detail})
            except Exception as exc:
                report.append({"ok": False, "message": str(exc)})
        succeeded = sum(1 for item in report if item["ok"])
        failed = len(report) - succeeded
        return {
            "ok": failed == 0,
            "message": (
                f"Deferred FHRP verification completed: {succeeded} succeeded, "
                f"{failed} failed."
            ),
            "report": report,
        }
