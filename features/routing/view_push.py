"""Routing-specific View & Push controller."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.view_push import BaseViewPushController, _variant_list


class RoutingViewPushController(BaseViewPushController):
    """Preview and apply pending Static/OSPF/EIGRP configuration for one host."""

    module_label = "Routing"

    def _module(self, module_name: str) -> str:
        return self.db._routing_module(module_name)

    def collect_pending_tasks(
        self, host: str, module_name: str = "all"
    ) -> list[dict[str, Any]]:
        self.db._sync_worker_paths()
        from features.routing.dispatcher import routing_dispatcher

        return routing_dispatcher(
            target_ip=self._clean_host(host),
            target_module=self._module(module_name),
            dry_run=True,
        ) or []

    def render_task_preview(
        self, task: dict[str, Any], module_name: str = "all"
    ) -> list[str]:
        from features.routing.worker import render_routing_config

        target = task.get("target", {}).get("ip", "")
        context = self.db._routing_device_context(target)
        sub_type = str(task.get("sub_type") or self._module(module_name)).lower()
        action = str(task.get("action") or "setup").lower()
        raw_config = task.get("config", [])
        configs = raw_config if isinstance(raw_config, list) else [raw_config]

        rendered = [f"# {target} / {sub_type.upper()} / {action.upper()}"]
        for config in configs:
            commands = render_routing_config(
                context["template_folder"], sub_type, config, action
            )
            lines = [
                line.strip()
                for line in commands.splitlines()
                if line.strip() and not line.strip().startswith("!")
            ]
            rendered.extend(self._redact_secrets(lines) or ["# No commands rendered."])
        return rendered

    def push_tasks(
        self, host: str, module_name: str, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        session_provider = self._session_provider_for_host(host)
        return self._push_tasks_with_provider(
            host, module_name, tasks, session_provider
        )

    def _push_without_reconcile(
        self,
        host: str,
        module_name: str,
        tasks: list[dict[str, Any]],
        connector: Any | None,
    ) -> dict[str, Any]:
        if connector is None:
            return self.push_tasks(host, module_name, tasks)
        return self._push_tasks_with_provider(
            host,
            module_name,
            tasks,
            lambda target: connector if target == host else None,
        )

    def _push_tasks_with_provider(
        self,
        host: str,
        module_name: str,
        tasks: list[dict[str, Any]],
        session_provider: Any,
    ) -> dict[str, Any]:
        self.db._sync_worker_paths()
        from infrastructure.network.config import TMP_DIR
        from features.routing.dispatcher import routing_dispatcher

        module = self._module(module_name)
        safe_host = host.replace(".", "_").replace(":", "_")
        log_path = Path(TMP_DIR) / f"routing_log_{module}_{safe_host}.json"
        # Never let a failed/aborted worker look successful by reading a report
        # left by an older Push operation.
        log_path.unlink(missing_ok=True)

        routing_dispatcher(
            target_ip=host,
            target_module=module,
            session_provider=session_provider,
        )

        if not log_path.is_file():
            return {
                "ok": False,
                "message": "Routing worker returned no result; pending database state was preserved.",
                "report": [],
            }
        try:
            raw_report = json.loads(log_path.read_text(encoding="utf-8"))
            report = raw_report if isinstance(raw_report, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "message": f"Could not read the routing Push result: {exc}",
                "report": [],
            }

        ok = bool(report) and all(
            str(item.get("status", "")).upper() == "SUCCESS" for item in report
        )
        if not report:
            return {
                "ok": False,
                "message": "Routing worker returned an empty result; pending database state was preserved.",
                "report": [],
            }

        detail = next(
            (
                str(item.get("log") or item.get("message") or "").strip()
                for item in report
                if str(item.get("status", "")).upper() != "SUCCESS"
                and str(item.get("log") or item.get("message") or "").strip()
            ),
            "",
        )
        return {
            "ok": ok,
            "message": (
                "Routing push completed."
                if ok
                else f"Routing push finished with errors: {detail}"
                if detail
                else "Routing push finished with errors."
            ),
            "report": _variant_list(report),
        }

    @staticmethod
    def _redact_secrets(lines: list[str]) -> list[str]:
        return [
            (
                " ".join([*line.split()[:-1], "<redacted>"])
                if "authentication-key" in line.lower()
                or "message-digest-key" in line.lower()
                else line
            )
            for line in lines
        ]
