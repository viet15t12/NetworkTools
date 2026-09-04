"""View & Push controller for per-device Cisco Syslog destinations."""

from __future__ import annotations

from typing import Any

from core.view_push import BaseViewPushController

from .device_config.commands import build_cancel_commands, build_enable_commands
from .device_config.service import SUPPORTED_DEVICE_OS
from .device_config.verifier import verify_destination, verify_source_interface
from .device_config.worker import CiscoSyslogWorker
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
        if context["template_folder"] not in SUPPORTED_DEVICE_OS:
            raise ValueError(
                "Syslog View & Push currently supports Cisco IOS/IOS-XE only"
            )
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
        commands = [
            command
            for task in tasks
            for command in list(task.get("commands") or [])
        ]
        execution = registry.execute(
            host,
            lambda connector: CiscoSyslogWorker(connector).send(commands),
            ensure_open=True,
        )
        ok = bool(execution.get("ok"))
        detail = str(
            execution.get("message")
            or ("Syslog commands accepted by the device." if ok else "Syslog apply failed.")
        )
        report = [
            {
                "ip": host,
                "module": "syslog",
                "entity": task.get("label", "Syslog destination"),
                "status": "SUCCESS" if ok else "FAIL",
                "success": ok,
                "log": detail,
                "db_updated": False,
            }
            for task in tasks
        ]
        return {
            "ok": ok,
            "success": ok,
            "message": (
                f"Applied {len(report)} Syslog server task(s); verification continues in background."
                if ok
                else f"Syslog push stopped: {detail}"
            ),
            "report": report,
        }

    def post_push_context(
        self, tasks: list[dict[str, Any]], result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return [
            {
                "action": str(task.get("action") or "setup"),
                "label": str(task.get("label") or "Syslog destination"),
                "config": {
                    key: (task.get("config") or {}).get(key)
                    for key in (
                        "server_ip",
                        "protocol",
                        "port",
                        "source_interface",
                        "trap_severity",
                        "timestamps",
                        "sequence_numbers",
                    )
                },
            }
            for task in tasks
        ]

    def verify_after_push(
        self,
        host: str,
        module_name: str,
        connector: Any,
        context: Any,
    ) -> dict[str, Any]:
        """Verify running/startup Syslog state and commit rows in the background."""
        tasks = [dict(task) for task in context] if isinstance(context, list) else []
        if not tasks:
            return {
                "ok": True,
                "skipped": True,
                "message": "No deferred Syslog verification was required.",
            }
        worker = CiscoSyslogWorker(connector)
        repository = self._repository()
        try:
            running = worker.show_logging(startup=False)
            startup = worker.show_logging(startup=True)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Deferred Syslog verification failed for {host}: {exc}",
                "report": [],
            }

        report: list[dict[str, Any]] = []
        for task in tasks:
            row = dict(task.get("config") or {})
            action = str(task.get("action") or "setup")
            server_ip = str(row.get("server_ip") or "")
            protocol = str(row.get("protocol") or "udp")
            port = int(row.get("port") or 514)
            interface = str(row.get("source_interface") or "")
            expected = action != "remove"
            messages = [
                verify_destination(output, server_ip, protocol, port, expected=expected)
                for output in (running, startup)
            ]
            if expected and interface and not all(
                verify_source_interface(output, interface)
                for output in (running, startup)
            ):
                messages.append(
                    f"Running/startup config does not contain logging source-interface {interface}."
                )
            failure = next((message for message in messages if message), "")
            if failure:
                attempt = getattr(repository, "save_device_attempt", None)
                if callable(attempt):
                    attempt(host, server_ip, protocol, port, failure)
                report.append({"ok": False, "message": failure})
                continue
            if expected:
                repository.save_device_state(
                    host,
                    server_ip,
                    protocol,
                    port,
                    interface,
                    True,
                    "Verified in running-config and startup-config.",
                    int(row.get("trap_severity") or 5),
                    bool(row.get("timestamps")),
                    bool(row.get("sequence_numbers")),
                )
            else:
                repository.delete_configuration_record(
                    host,
                    server_ip,
                    protocol,
                    port,
                )
            report.append({"ok": True, "message": "Syslog state verified."})

        succeeded = sum(1 for item in report if item["ok"])
        failed = len(report) - succeeded
        return {
            "ok": failed == 0,
            "message": (
                f"Deferred Syslog verification completed: {succeeded} succeeded, "
                f"{failed} failed."
            ),
            "report": report,
        }


__all__ = ["SyslogViewPushController"]
