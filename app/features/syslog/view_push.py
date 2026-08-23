"""View & Push controller for per-device Cisco Syslog destinations."""

from __future__ import annotations

from typing import Any

from core.view_push import BaseViewPushController

from .device_config.commands import build_cancel_commands, build_enable_commands
from .device_config.service import SyslogConfigurator
from .repository import SyslogRepository


class _ConnectorRegistry:
    """Adapt the connector already locked by BaseViewPushController."""

    def __init__(self, connector: Any) -> None:
        self.connector = connector

    def execute(self, host: str, operation: Any, *, ensure_open: bool = True) -> dict[str, Any]:
        return {"ok": True, "value": operation(self.connector)}


class SyslogViewPushController(BaseViewPushController):
    """Preview and reconcile every pending Syslog server row for one device."""

    module_label = "Syslog"

    def _repository(self) -> SyslogRepository:
        return SyslogRepository(self.db.info_db_path, self.db.db_path)

    @staticmethod
    def _commands(row: dict[str, Any]) -> list[str]:
        if str(row.get("sync_status") or "pending_apply") == "pending_delete":
            return build_cancel_commands(
                str(row["server_ip"]), str(row["protocol"]), int(row["port"])
            )
        return build_enable_commands(
            str(row["server_ip"]),
            str(row["protocol"]),
            int(row["port"]),
            str(row.get("source_interface") or ""),
            int(row.get("trap_severity", 5)),
            bool(row.get("timestamps")),
            bool(row.get("sequence_numbers")),
        )

    def collect_pending_tasks(
        self, host: str, module_name: str = "all"
    ) -> list[dict[str, Any]]:
        clean_host = self._clean_host(host)
        if not clean_host:
            return []
        context = self.db._routing_device_context(clean_host)
        if context["template_folder"] != "cisco_ios":
            raise ValueError("Syslog View & Push currently supports Cisco IOS/IOS-XE only")
        tasks: list[dict[str, Any]] = []
        for row in self._repository().device_configurations(clean_host):
            state = str(row.get("sync_status") or "pending_apply")
            if state not in {"pending_apply", "pending_delete"}:
                continue
            tasks.append(
                {
                    "target": {"ip": clean_host},
                    "module": "servers",
                    "action": "remove" if state == "pending_delete" else "setup",
                    "label": (
                        f"{row['server_ip']} / {str(row['protocol']).upper()}:{row['port']}"
                    ),
                    "config": row,
                    "commands": self._commands(row),
                    "success": state,
                }
            )
        return tasks

    def render_task_preview(
        self, task: dict[str, Any], module_name: str = "all"
    ) -> list[str]:
        return [
            f"# {task['target']['ip']} / SYSLOG / {str(task['action']).upper()} / {task['label']}",
            *task["commands"],
        ]

    def push_tasks(
        self, host: str, module_name: str, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self._apply_tasks(host, tasks, self._session_registry)

    def _push_and_reconcile(
        self,
        host: str,
        module_name: str,
        tasks: list[dict[str, Any]],
        connector: Any | None,
    ) -> dict[str, Any]:
        # BaseViewPushController already owns the host session here. Re-entering
        # SessionRegistry.execute from SyslogConfigurator would deadlock on the
        # same per-host lock, so adapt the connector that is already protected.
        if connector is None:
            return self.push_tasks(host, module_name, tasks)
        result = self._apply_tasks(host, tasks, _ConnectorRegistry(connector))
        if not bool(result.get("ok")) or not result.get("report"):
            return result

        reconcile = getattr(self.db, "reconcileViewPushSnapshot", None)
        if not callable(reconcile):
            return result
        reconciliation = dict(reconcile(host, connector) or {})
        result["reconciliation"] = reconciliation
        original = str(result.get("message") or "Syslog push completed.")
        if reconciliation.get("ok"):
            result["message"] = f"{original} {reconciliation.get('message', '')}".strip()
        else:
            result["severity"] = "warning"
            detail = str(
                reconciliation.get("message")
                or "Post-push persistence and synchronization failed."
            )
            result["message"] = f"{original} Warning: {detail}"
        return result

    def _push_without_reconcile(
        self,
        host: str,
        module_name: str,
        tasks: list[dict[str, Any]],
        connector: Any | None,
    ) -> dict[str, Any]:
        # The base class already owns this connector's per-host lock.
        if connector is None:
            return self.push_tasks(host, module_name, tasks)
        return self._apply_tasks(host, tasks, _ConnectorRegistry(connector))

    def _apply_tasks(
        self, host: str, tasks: list[dict[str, Any]], registry: Any
    ) -> dict[str, Any]:
        repository = self._repository()
        configurator = SyslogConfigurator(repository, registry)
        report: list[dict[str, Any]] = []

        for task in tasks:
            row = dict(task.get("config") or {})
            action = str(task.get("action") or "setup")
            if action == "remove":
                result = configurator.cancel(
                    host, str(row["server_ip"]), str(row["protocol"]), int(row["port"])
                )
                if bool(result.get("ok")):
                    repository.delete_configuration_record(
                        host, str(row["server_ip"]), str(row["protocol"]), int(row["port"])
                    )
            else:
                result = configurator.configure(
                    host,
                    str(row["server_ip"]),
                    str(row["protocol"]),
                    int(row["port"]),
                    str(row.get("source_interface") or ""),
                    int(row.get("trap_severity", 5)),
                    bool(row.get("timestamps")),
                    bool(row.get("sequence_numbers")),
                )

            ok = bool(result.get("ok"))
            report.append(
                {
                    "ip": host,
                    "module": "syslog",
                    "entity": task.get("label", "Syslog destination"),
                    "status": "SUCCESS" if ok else "FAIL",
                    "success": ok,
                    "log": str(result.get("message") or ""),
                    "db_updated": ok,
                }
            )
            if not ok:
                break

        ok = bool(report) and all(bool(item["success"]) for item in report)
        detail = next((item["log"] for item in report if not item["success"]), "")
        return {
            "ok": ok,
            "success": ok,
            "message": (
                f"Applied {len(report)} Syslog server task(s)."
                if ok
                else f"Syslog push stopped: {detail}"
            ),
            "report": report,
        }


__all__ = ["SyslogViewPushController"]
