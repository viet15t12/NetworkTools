from __future__ import annotations

from contextlib import closing
from typing import Any

from core.view_push import BaseViewPushController

from .commands import render_commands
from .desired_state import collect_vtp_state
from .interface_task_builder import build_interface_tasks
from .policy_task_builder import build_security_tasks, build_stp_tasks
from .schema import ensure_switch_schema
from .success_repository import mark_task_success
from .sync import parse_vtp_status, sync_switch_state
from .vtp_membership import vlan_vtp_clients, vlan_vtp_context
from .worker import apply_commands


PUBLIC_MODULES = (
    "vlan",
    "svi",
    "interfaces",
    "etherchannel",
    "stp",
    "vtp",
    "l2_security",
    "port_security",
)


class SwitchingViewPushController(BaseViewPushController):
    """Build and apply granular switching tasks scoped to the active tab."""

    module_label = "Switching"

    def reconciliation_options(self, module_name: str) -> dict[str, Any]:
        """Refresh the complete bounded switch snapshot after every Push."""
        return {"switch_state_keys": None}

    def _modules(self, module_name: str) -> tuple[str, ...]:
        normalized = (module_name or "all").strip().lower()
        if normalized == "all":
            return PUBLIC_MODULES
        if normalized not in PUBLIC_MODULES:
            raise ValueError(f"Unsupported Layer 2 module: {module_name}")
        return (normalized,)

    def _check_platform(self, host: str) -> None:
        context = self.db._routing_device_context(host)
        if context["template_folder"] != "cisco_ios":
            raise ValueError(
                f"Layer 2 View & Push currently supports Cisco IOS only, not {context['platform']}"
            )

    @staticmethod
    def _task(
        host: str,
        module: str,
        entity_key: str,
        label: str,
        payload: dict[str, Any],
        commands: list[str],
        tracking: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "target": {"ip": host},
            "module": module,
            "entity_key": entity_key,
            "label": label,
            "config": payload,
            "commands": commands,
            "tracking": tracking or {},
            "success": "pending_apply",
        }

    def _vlan_tasks(self, host: str) -> list[dict[str, Any]]:
        context = vlan_vtp_context(self.db, host)
        if context is not None and str(context["mode"]).lower() == "client":
            return []
        with closing(self.db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, vlan_id, vlan_name, state, success
                FROM t06_vlan_db
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                )
                ORDER BY vlan_id;
                """,
                (host,),
            ).fetchall()
        tasks = []
        for source in rows:
            row = dict(source)
            row_id = int(row.pop("id"))
            success = str(row.pop("success") or "pending_apply")
            row["action"] = "remove" if success == "pending_delete" else "setup"
            payload = {"vlans": [row]}
            tasks.append(self._task(
                host, "vlan", f"vlan:{row['vlan_id']}", f"VLAN {row['vlan_id']}",
                payload, render_commands("vlan", payload),
                {"success_rows": [{
                    "kind": "vlan",
                    "id": row_id,
                    "action": "delete" if success == "pending_delete" else "sync",
                }]},
            ))
            tasks[-1]["success"] = success
        return tasks

    def _svi_tasks(self, host: str) -> list[dict[str, Any]]:
        with closing(self.db._connect()) as conn:
            routing = conn.execute(
                "SELECT host, ip_routing, sync_status "
                "FROM t06_switch_l3_config WHERE host = ? "
                "AND sync_status IN ('pending_apply', 'pending_delete');",
                (host,),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT id, vlan_id, ip_address, subnet_mask, shutdown, sync_status
                FROM t06_svi_interface
                WHERE host = ? AND sync_status IN ('pending_apply', 'pending_delete')
                ORDER BY vlan_id;
                """,
                (host,),
            ).fetchall()

        tasks: list[dict[str, Any]] = []
        if routing is not None:
            payload = {"ip_routing": bool(routing["ip_routing"]), "svis": []}
            tasks.append(
                self._task(
                    host,
                    "svi",
                    "global:ip-routing",
                    "IP routing",
                    payload,
                    render_commands("svi", payload),
                    {"success_rows": [{"kind": "switch_l3", "id": host}]},
                )
            )
            tasks[-1]["success"] = str(routing["sync_status"])

        for source in rows:
            row = dict(source)
            row_id = int(row.pop("id"))
            sync_status = str(row.pop("sync_status") or "pending_apply")
            row["action"] = "remove" if sync_status == "pending_delete" else "setup"
            payload = {"svis": [row]}
            tasks.append(
                self._task(
                    host,
                    "svi",
                    f"svi:{row['vlan_id']}",
                    f"SVI Vlan{row['vlan_id']}",
                    payload,
                    render_commands("svi", payload),
                    {"success_rows": [{
                        "kind": "svi",
                        "id": row_id,
                        "action": "delete" if sync_status == "pending_delete" else "sync",
                    }]},
                )
            )
            tasks[-1]["success"] = sync_status
        return tasks

    def _interface_tasks(self, host: str) -> list[dict[str, Any]]:
        return build_interface_tasks(self.db, host, self._task)

    def _etherchannel_tasks(self, host: str) -> list[dict[str, Any]]:
        with closing(self.db._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, po_number, protocol, mode, member_ports,
                       cleanup_member_ports, description, success
                FROM t06_etherchannel
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                )
                ORDER BY po_number;
                """,
                (host,),
            ).fetchall()
            interface_rows = conn.execute(
                "SELECT id, if_name FROM t06_interface_l2 WHERE host = ?;",
                (host,),
            ).fetchall()
        logical_interface_ids: dict[int, int] = {}
        for interface in interface_rows:
            name = str(interface["if_name"] or "").strip().lower()
            compact = name.replace("-", "").replace(" ", "")
            prefix = "portchannel" if compact.startswith("portchannel") else "po"
            suffix = compact[len(prefix):] if compact.startswith(prefix) else ""
            if suffix.isdigit():
                logical_interface_ids[int(suffix)] = int(interface["id"])
        tasks: list[dict[str, Any]] = []
        valid_modes = {
            "lacp": {"active", "passive"},
            "pagp": {"desirable", "auto"},
            "static": {"on"},
        }
        for source in rows:
            row = dict(source)
            row_id = int(row.pop("id"))
            success = str(row.pop("success") or "pending_apply")
            row["action"] = "remove" if success == "pending_delete" else "setup"
            if success != "pending_delete" and (
                row["protocol"] not in valid_modes
                or row["mode"] not in valid_modes[row["protocol"]]
            ):
                raise ValueError(
                    "EtherChannel protocol/mode mismatch on Port-channel"
                    f"{row['po_number']}"
                )
            payload = {"interfaces": [], "etherchannels": [row]}
            success_rows = [{
                "kind": "etherchannel",
                "id": row_id,
                "action": "delete" if success == "pending_delete" else "sync",
            }]
            logical_interface_id = logical_interface_ids.get(int(row["po_number"]))
            if success == "pending_delete" and logical_interface_id is not None:
                success_rows.append({
                    "kind": "interface",
                    "id": logical_interface_id,
                    "action": "delete",
                })
            tasks.append(
                self._task(
                    host,
                    "etherchannel",
                    f"port-channel:{row['po_number']}",
                    f"Port-channel{row['po_number']}",
                    payload,
                    render_commands("interfaces", payload),
                    {"success_rows": success_rows},
                )
            )
            tasks[-1]["success"] = success
        return tasks

    def _stp_tasks(self, host: str) -> list[dict[str, Any]]:
        return build_stp_tasks(self.db, host, self._task)

    def _vtp_tasks(self, host: str) -> list[dict[str, Any]]:
        with closing(self.db._connect()) as conn:
            pending = conn.execute(
                """
                SELECT vtp_switch_id, success FROM t09_vtp_switches
                WHERE host = ? AND (
                    success IN ('pending_apply','pending_delete') OR success IS NULL
                );
                """,
                (host,),
            ).fetchall()
            if not pending:
                return []
            payload = collect_vtp_state(conn, host)
        if not payload["vtp"]:
            return []
        task = [
            self._task(
                host,
                "vtp",
                "database:vlan",
                "VTP VLAN database",
                payload,
                render_commands("vtp", payload),
                {"success_rows": [
                    {"kind": "vtp", "id": int(row["vtp_switch_id"])}
                    for row in pending
                ]},
            )
        ]
        task[0]["success"] = str(pending[0]["success"])
        return task

    def _security_tasks(self, host: str, module: str) -> list[dict[str, Any]]:
        return build_security_tasks(self.db, host, module, self._task)

    def _candidate_tasks(self, host: str, module: str) -> list[dict[str, Any]]:
        if module == "vlan":
            return self._vlan_tasks(host)
        if module == "svi":
            return self._svi_tasks(host)
        if module == "interfaces":
            return self._interface_tasks(host)
        if module == "etherchannel":
            return self._etherchannel_tasks(host)
        if module == "stp":
            return self._stp_tasks(host)
        if module == "vtp":
            return self._vtp_tasks(host)
        return self._security_tasks(host, module)

    def collect_pending_tasks(
        self, host: str, module_name: str = "all"
    ) -> list[dict[str, Any]]:
        self._check_platform(host)
        ensure_switch_schema(self.db)
        tasks: list[dict[str, Any]] = []
        for module in self._modules(module_name):
            tasks.extend(self._candidate_tasks(host, module))
        return tasks

    def render_task_preview(
        self, task: dict[str, Any], module_name: str = "all"
    ) -> list[str]:
        return [
            f"# {task['target']['ip']} / SWITCHING / {task['label']}",
            *task["commands"],
        ]

    def pending_state(self, host: str, module_name: str = "all") -> dict[str, Any]:
        result = super().pending_state(host, module_name)
        result["success"] = bool(result.get("ok"))
        return result

    def preview(self, host: str, module_name: str = "all") -> dict[str, Any]:
        result = super().preview(host, module_name)
        result["success"] = bool(result.get("ok"))
        return result

    def push(self, host: str, module_name: str = "all") -> dict[str, Any]:
        result = super().push(host, module_name)
        result["success"] = bool(result.get("ok"))
        return result

    def reconcile_after_push(
        self, host: str, module_name: str = "all"
    ) -> dict[str, Any]:
        """Reconcile the server first, then its clients after a VLAN Push."""
        result = super().reconcile_after_push(host, module_name)
        return self._append_vtp_client_reconciliation(host, module_name, result)

    def _push_and_reconcile(
        self,
        host: str,
        module_name: str,
        tasks: list[dict[str, Any]],
        connector: Any | None,
    ) -> dict[str, Any]:
        """Preserve the synchronous Push path's server-before-client ordering."""
        result = super()._push_and_reconcile(
            host, module_name, tasks, connector
        )
        return self._append_vtp_client_reconciliation(host, module_name, result)

    def _append_vtp_client_reconciliation(
        self, host: str, module_name: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        normalized_module = str(module_name or "all").strip().lower()
        own_reconciliation = result.get("reconciliation")
        if (
            normalized_module not in {"all", "vlan"}
            or not bool(result.get("ok"))
            or not isinstance(own_reconciliation, dict)
            or not bool(own_reconciliation.get("ok"))
        ):
            return result

        context = vlan_vtp_context(self.db, host)
        if context is None or str(context["mode"]).lower() != "server":
            return result

        client_sync = self._reconcile_vtp_clients(
            host, str(context["domain_name"])
        )
        result["vtpClientReconciliation"] = client_sync
        if client_sync["total"] == 0:
            return result

        original = str(result.get("message") or "VLAN Push synchronized.")
        if client_sync["ok"]:
            result["message"] = (
                f"{original} Synchronized {client_sync['success']} VTP client(s) "
                f"in domain {context['domain_name']}."
            )
        else:
            result["severity"] = "warning"
            result["message"] = (
                f"{original} Warning: synchronized {client_sync['success']} of "
                f"{client_sync['total']} VTP client(s) in domain "
                f"{context['domain_name']}."
            )
        return result

    def _reconcile_vtp_clients(
        self, server_host: str, expected_domain: str
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for client_host in vlan_vtp_clients(self.db, server_host):
            try:
                if self._managed_session:
                    executed = self._session_registry.execute(
                        client_host,
                        lambda connector, target=client_host: self._sync_vtp_client(
                            target, expected_domain, connector
                        ),
                    )
                    if not bool(executed.get("ok")):
                        raise RuntimeError(
                            str(
                                executed.get("message")
                                or f"Could not collect VTP client {client_host}"
                            )
                        )
                    detail = dict(executed.get("value") or {})
                else:
                    provider = self._session_provider_for_host(client_host)
                    if provider is None:
                        raise ValueError(
                            "Layer 2 RESTCONF client synchronization is not implemented"
                        )
                    connector = provider(client_host)
                    if connector is None:
                        raise RuntimeError(
                            f"Could not open a device session for {client_host}"
                        )
                    detail = self._sync_vtp_client(
                        client_host, expected_domain, connector
                    )
                results.append(
                    {"host": client_host, "ok": True, "summary": detail}
                )
            except Exception as exc:
                results.append(
                    {"host": client_host, "ok": False, "message": str(exc)}
                )

        succeeded = sum(1 for item in results if item["ok"])
        return {
            "ok": succeeded == len(results),
            "domain": expected_domain,
            "total": len(results),
            "success": succeeded,
            "failed": len(results) - succeeded,
            "results": results,
        }

    def _sync_vtp_client(
        self, host: str, expected_domain: str, connector: Any
    ) -> dict[str, Any]:
        collected = dict(
            connector.collect_switch_state(("vtp_status", "vlan_brief")) or {}
        )
        if not bool(collected.get("ok")):
            raise RuntimeError(
                str(
                    collected.get("message")
                    or f"Could not collect VTP client state from {host}"
                )
            )
        snapshot = dict(collected.get("outputs") or {})
        status = parse_vtp_status(snapshot.get("vtp_status", ""))
        if status is None:
            raise ValueError(f"{host} did not return a configured VTP domain")
        actual_domain = str(status["domain_name"])
        if actual_domain.casefold() != expected_domain.casefold():
            raise ValueError(
                f"{host} reported VTP domain {actual_domain}, expected {expected_domain}"
            )
        if str(status["mode"]).lower() != "client":
            raise ValueError(
                f"{host} reported VTP mode {status['mode']}, expected client"
            )

        db_path = getattr(self.db, "db_path", None) or getattr(
            self.db, "path", None
        )
        if db_path is None:
            raise RuntimeError("The active device database path is unavailable")
        return dict(
            sync_switch_state(
                db_path,
                host,
                snapshot,
                mode="force_device_state",
            )
            or {}
        )

    def push_tasks(
        self, host: str, module_name: str, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        provider = self._session_provider_for_host(host)
        if provider is None:
            raise ValueError("Layer 2 RESTCONF push is not implemented")
        connector = provider(host)
        if connector is None:
            raise RuntimeError(f"Could not open a device session for {host}")

        report: list[dict[str, Any]] = []
        # One Netmiko config transaction is materially faster on serial/virtual
        # IOS sessions than entering and leaving configuration mode once per
        # database row. Renderers terminate their interface/VLAN submodes, so
        # task boundaries remain safe inside this combined command stream.
        commands = [command for task in tasks for command in task["commands"]]
        try:
            output = apply_commands(connector, commands)
            for task in tasks:
                mark_task_success(self.db, task.get("tracking") or {})
                report.append(
                    {
                        "ip": host,
                        "module": task["module"],
                        "entity": task["entity_key"],
                        "status": "SUCCESS",
                        "success": True,
                        "log": output,
                        "db_updated": True,
                    }
                )
        except Exception as exc:
            task = tasks[0]
            report.append(
                {
                    "ip": host,
                    "module": task["module"],
                    "entity": task["entity_key"],
                    "status": "FAIL",
                    "success": False,
                    "log": str(exc),
                    "db_updated": False,
                }
            )

        success = bool(report) and all(item["success"] for item in report)
        detail = next((item["log"] for item in report if not item["success"]), "")
        return {
            "ok": success,
            "success": success,
            "message": (
                f"Applied {len(report)} switching task(s)."
                if success
                else f"Switching push stopped: {detail}"
            ),
            "report": report,
        }
