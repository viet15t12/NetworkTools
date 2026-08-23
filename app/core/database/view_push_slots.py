"""QML slots grouped by the view push responsibility."""

from __future__ import annotations

import sys
import time
from typing import Any

from PyQt6.QtCore import pyqtSlot

from .conversion import _variant_list


class ViewPushSlotsMixin:
    """Provide the stable QML contract for this responsibility."""

    def _start_background_task(
        self,
        task_key: str,
        controller_name: str,
        host: str,
        module_name: str,
        start_message: str,
        callback: Any,
        operation: str = "push",
    ) -> bool:
        """Start one keyed preview/push task and retain its QML routing metadata."""
        if task_key in self._background_tasks:
            message = f"A push task is already running for {host}."
            self.taskFinished.emit(False, message)
            return False

        self._background_tasks[task_key] = {
            "controller": controller_name,
            "host": host,
            "module": module_name,
            "operation": operation,
        }

        started = self._task_coordinator.start(
            task_key,
            start_message,
            callback,
            on_started=self._relay_task_started,
            on_progress=self._relay_task_progress,
            on_finished=self._handle_background_task_finished,
        )
        if not started:
            self._background_tasks.pop(task_key, None)
        return started

    @pyqtSlot(str)
    def _relay_task_started(self, message: str) -> None:
        """Relay coordinator start messages through the public facade signal."""
        self.taskStarted.emit(message)

    @pyqtSlot(str)
    def _relay_task_progress(self, message: str) -> None:
        """Relay coordinator progress messages through the public facade signal."""
        self.taskProgress.emit(message)

    @pyqtSlot(str, bool, str, object)
    def _handle_background_task_finished(self, task_key: str, ok: bool, message: str, result: object) -> None:
        """Emit the matching preview or push completion signals for a task."""
        entry = self._background_tasks.pop(task_key, {})
        controller = str(entry.get("controller") or "")
        host = str(entry.get("host") or "")
        module = str(entry.get("module") or "")
        operation = str(entry.get("operation") or "push")
        if operation == "preview":
            commands = str(result.get("commands") or "") if isinstance(result, dict) else ""
            self.viewPushPreviewFinished.emit(controller, host, module, ok, message, commands)
        elif operation not in {"batch", "post-push-batch", "post-push-single"}:
            self.viewPushFinished.emit(controller, host, module, ok, message)
            if self._snapshot_was_updated(result):
                self.runningConfigUpdated.emit(host)
        if operation == "post-push-single" and self._snapshot_was_updated(result):
            self.runningConfigUpdated.emit(host)
        if operation in {"batch", "post-push-batch"} and isinstance(result, dict):
            for item in result.get("results", []):
                if isinstance(item, dict) and self._snapshot_was_updated(item):
                    updated_host = str(item.get("host") or "").strip()
                    if updated_host:
                        self.runningConfigUpdated.emit(updated_host)
        self.taskFinished.emit(ok, message)
        if (
            operation == "push"
            and isinstance(result, dict)
            and result.get("ok")
            and result.get("postPushPending")
            and host
        ):
            self._start_post_push_single(controller, host, module)
        if operation == "batch" and isinstance(result, dict):
            deferred_hosts = [
                str(item.get("host") or "").strip()
                for item in result.get("results", [])
                if isinstance(item, dict)
                and item.get("ok")
                and item.get("postPushPending")
                and str(item.get("host") or "").strip()
            ]
            if deferred_hosts:
                self._start_post_push_batch(controller, module, deferred_hosts)

    def _start_post_push_single(
        self, controller: str, host: str, module: str
    ) -> bool:
        """Synchronize one successfully applied device without holding its dialog."""
        task_key = (
            f"post-view-push:{controller}:{host}:{module}:{time.monotonic_ns()}"
        )

        def run_reconciliation(progress: Any) -> dict[str, Any]:
            progress(f"Synchronizing device state for {host} in background...")
            return dict(
                self._view_push.get(controller).reconcile_after_push(host, module)
                or {}
            )

        return self._start_background_task(
            task_key,
            controller,
            host,
            module,
            f"Synchronizing {host} in background...",
            run_reconciliation,
            "post-push-single",
        )

    def _start_post_push_batch(
        self, controller: str, module: str, hosts: list[str]
    ) -> bool:
        """Start deferred show/save/snapshot work after the apply dialog completes."""
        # Keep each deferred pass distinct. A user may start another batch while
        # the previous pass is still collecting snapshots; per-host session
        # locks serialize only the devices that overlap.
        task_key = f"post-view-push-batch:{controller}:{module}:{id(hosts)}"

        def run_reconciliation(progress: Any) -> dict[str, Any]:
            def host_changed(host: str, state: str, _message: str, _value: int) -> None:
                if state == "running":
                    progress(f"Synchronizing device state for {host} in background...")

            def batch_progress(
                completed: int, success: int, failed: int, total: int
            ) -> None:
                progress(
                    f"Background synchronization: {completed}/{total} completed, "
                    f"{success} succeeded, {failed} failed."
                )

            return self._view_push_batch.reconcile(
                controller,
                module,
                hosts,
                on_host=host_changed,
                on_progress=batch_progress,
            )

        return self._start_background_task(
            task_key,
            controller,
            "",
            module,
            f"Synchronizing {len(hosts)} device(s) in background...",
            run_reconciliation,
            "post-push-batch",
        )

    @staticmethod
    def _snapshot_was_updated(result: object) -> bool:
        """Return whether a completed Push committed a fresh config snapshot."""
        if not isinstance(result, dict):
            return False
        reconciliation = result.get("reconciliation")
        return bool(
            isinstance(reconciliation, dict)
            and reconciliation.get("snapshotUpdated")
        )

    def _sync_worker_paths(self) -> None:
        """Synchronize the compatibility worker config with this manager."""
        from infrastructure.network import config

        config.DB_PATH = str(self.db_path.resolve())

    def _is_view_push_dev_host(self, host: str) -> bool:
        """Return whether Push must stay in the no-network development path."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(dev, 0) AS dev FROM t01_devices WHERE host = ?;",
                (str(host or "").strip(),),
            ).fetchone()
        return bool(row and int(row["dev"] or 0) == 1)

    def reconcileViewPushSnapshot(
        self,
        host: str,
        connector: Any,
        switch_state_keys: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        """Delegate the post-push lifecycle to its application service."""
        post_push = getattr(self, "_post_push_service", None)
        if post_push is not None:
            return dict(
                post_push.reconcile(
                    host,
                    connector,
                    switch_state_keys=switch_state_keys,
                )
                or {}
            )

        # Compatibility for lightweight adapters that still compose this mixin
        # without DatabaseManager. The running app always uses PostPushService.
        service = getattr(self, "_config_sync_service", None)
        if service is None:
            return {
                "ok": False,
                "message": "Post-push running-config sync service is unavailable.",
            }
        snapshot = connector.collect_running_config()
        if not bool(snapshot.get("ok")):
            return {
                "ok": False,
                "message": str(
                    snapshot.get("message")
                    or getattr(connector, "last_error", "")
                    or "Could not collect running-config after Push."
                ),
            }
        running_config = str(snapshot.get("running_config") or "")
        if not running_config.strip():
            return {
                "ok": False,
                "message": "The device returned an empty running-config after Push.",
            }
        backup = self._config_backup_service.save_snapshot(host, running_config)
        if not bool(backup.get("ok")):
            return {
                "ok": False,
                "message": str(backup.get("message") or "Post-push backup failed."),
            }
        sync = service.sync_manual_snapshot(
            host,
            running_config,
            str(snapshot.get("interface_brief") or ""),
            backup,
            mode="force_device_state",
        )
        return {
            "ok": bool(sync.get("ok")),
            "message": str(
                sync.get("message")
                or "Running-config collected and database synchronized after Push."
            ),
            "backup": backup,
            "sync": sync,
            "snapshotUpdated": bool(backup.get("ok")),
        }

    def _routing_device_context(self, host: str) -> dict[str, str]:
        """Resolve routing platform and transport metadata for template rendering."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT os, method
                FROM t01_devices
                WHERE host = ?;
                """,
                (host,),
            ).fetchone()
        if row is None:
            return {"platform": "cisco_ios", "template_folder": "cisco_ios", "method": "SSH"}
        os_name = (row["os"] or "cisco_ios").strip()
        platform = "cisco_ios" if os_name == "cisco" else os_name
        template_folder = "cisco_ios" if platform == "cisco_ios_telnet" else platform
        return {
            "platform": platform,
            "template_folder": template_folder,
            "method": (row["method"] or "SSH").strip().upper(),
        }

    def _routing_module(self, module_name: str) -> str:
        """Normalize a requested routing module to the supported dispatcher values."""
        text = (module_name or "all").strip().lower()
        return text if text in {"static", "ospf", "eigrp", "all"} else "all"

    @pyqtSlot(str, str, result="QVariant")
    def previewRoutingConfig(self, host: str, module_name: str) -> dict[str, Any]:
        """Render thử cấu hình routing từ DB mà không push xuống thiết bị."""
        host = (host or "").strip()
        if not host:
            return {"ok": False, "message": "Host is empty.", "commands": "", "tasks": []}

        try:
            self._sync_worker_paths()
            from features.routing.dispatcher import routing_dispatcher
            from features.routing.worker import render_routing_config

            module = self._routing_module(module_name)
            tasks = routing_dispatcher(target_ip=host, target_module=module, dry_run=True) or []
            if not tasks:
                return {"ok": True, "message": "No pending routing configuration to push.", "commands": "", "tasks": []}

            rendered: list[str] = []
            for task in tasks:
                target = task.get("target", {}).get("ip", host)
                context = self._routing_device_context(target)
                sub_type = str(task.get("sub_type") or module).lower()
                action = str(task.get("action") or "setup").lower()
                raw_config = task.get("config", [])
                configs = raw_config if isinstance(raw_config, list) else [raw_config]
                rendered.append(f"# {target} / {sub_type.upper()} / {action.upper()}")
                for cfg in configs:
                    commands = render_routing_config(context["template_folder"], sub_type, cfg, action)
                    lines = [line.strip() for line in commands.splitlines() if line.strip() and not line.strip().startswith("!")]
                    rendered.extend(lines or ["# No commands rendered."])
                rendered.append("")

            return {
                "ok": True,
                "message": f"Prepared {len(tasks)} routing task(s).",
                "commands": "\n".join(rendered).strip(),
                "tasks": _variant_list(tasks),
            }
        except Exception as exc:
            message = f"Preview routing failed: {exc}"
            self._set_last_routing_error(message)
            print(f"[db] {message}", file=sys.stderr)
            return {"ok": False, "message": message, "commands": "", "tasks": []}

    @pyqtSlot(str, str, result="QVariant")
    def pushRoutingConfig(self, host: str, module_name: str) -> dict[str, Any]:
        """Push cấu hình routing pending xuống thiết bị hoặc luồng dev tương ứng."""
        host = (host or "").strip()
        if not host:
            return {"ok": False, "message": "Host is empty.", "report": []}

    @pyqtSlot(str, str, str, result=bool)
    def hasPendingViewPush(self, controller_name: str, host: str, module_name: str) -> bool:
        """Return whether a controller has staged configuration for a host."""
        if getattr(self, "_shutting_down", False):
            return False
        try:
            return self._view_push.get(controller_name).has_pending(host, module_name)
        except Exception as exc:
            print(f"[db] hasPendingViewPush failed: {exc}", file=sys.stderr)
            return False

    @pyqtSlot(str, str, str, result="QVariant")
    def previewViewPush(self, controller_name: str, host: str, module_name: str) -> dict[str, Any]:
        """Render staged configuration without sending it to the device."""
        try:
            return self._view_push.get(controller_name).preview(host, module_name)
        except Exception as exc:
            message = f"Preview {controller_name} failed: {exc}"
            if (controller_name or "").strip().lower() == "routing":
                self._set_last_routing_error(message)
            print(f"[db] {message}", file=sys.stderr)
            return {"ok": False, "message": message, "commands": "", "tasks": []}

    @pyqtSlot(str, str, str, result=bool)
    def previewViewPushAsync(self, controller_name: str, host: str, module_name: str) -> bool:
        """Schedule an asynchronous preview while preserving public QML signals."""
        controller = (controller_name or "").strip().lower()
        target_host = (host or "").strip()
        module = (module_name or "all").strip().lower() or "all"
        if not controller or not target_host:
            message = "Preview failed: controller or host is empty."
            self.viewPushPreviewFinished.emit(controller, target_host, module, False, message, "")
            self.taskFinished.emit(False, message)
            return False

        task_key = f"view-preview:{controller}:{target_host}:{module}"
        start_message = f"Preparing {controller.upper()} configuration preview for {target_host}..."

        def run_preview(progress: Any) -> dict[str, Any]:
            """Render the requested preview inside the shared task coordinator."""
            progress(f"Rendering {controller.upper()} template for {target_host}...")
            result = self.previewViewPush(controller, target_host, module)
            progress(f"Finished {controller.upper()} preview for {target_host}.")
            return result

        return self._start_background_task(
            task_key,
            controller,
            target_host,
            module,
            start_message,
            run_preview,
            "preview",
        )

    @pyqtSlot(str, str, str, result="QVariant")
    def pushViewPush(self, controller_name: str, host: str, module_name: str) -> dict[str, Any]:
        """Push staged configuration through the selected feature controller."""
        try:
            return self._view_push.get(controller_name).push(host, module_name)
        except Exception as exc:
            message = f"Push {controller_name} failed: {exc}"
            if (controller_name or "").strip().lower() == "routing":
                self._set_last_routing_error(message)
            print(f"[db] {message}", file=sys.stderr)
            return {"ok": False, "message": message, "report": []}

    @pyqtSlot(str, str, str, result=bool)
    def pushViewPushAsync(self, controller_name: str, host: str, module_name: str) -> bool:
        """Schedule an asynchronous push while preserving public QML signals."""
        controller = (controller_name or "").strip().lower()
        target_host = (host or "").strip()
        module = (module_name or "all").strip().lower() or "all"
        if not controller or not target_host:
            message = "Push failed: controller or host is empty."
            self.viewPushFinished.emit(controller, target_host, module, False, message)
            self.taskFinished.emit(False, message)
            return False

        task_key = f"view-push:{controller}:{target_host}:{module}"
        start_message = f"Pushing {controller.upper()} configuration to {target_host}..."

        def run_push(progress: Any) -> dict[str, Any]:
            """Execute the requested push inside the shared task coordinator."""
            progress(f"Rendering {controller.upper()} configuration for {target_host}...")
            try:
                result = self._view_push.get(controller).push_apply_only(
                    target_host, module
                )
            except Exception as exc:
                result = {
                    "ok": False,
                    "message": f"Push {controller} failed: {exc}",
                    "report": [],
                }
            progress(f"Finished {controller.upper()} push for {target_host}.")
            return result

        return self._start_background_task(
            task_key,
            controller,
            target_host,
            module,
            start_message,
            run_push,
        )

    @pyqtSlot(str, "QVariant", str, result=bool)
    def pushViewPushBatchAsync(
        self, controller_name: str, hosts: Any, module_name: str
    ) -> bool:
        """Push several hosts concurrently while isolating each host result."""
        controller = (controller_name or "").strip().lower()
        module = (module_name or "all").strip().lower() or "all"
        targets = self._view_push_batch.normalize_hosts(hosts)
        if not controller or not targets:
            message = "Batch Push failed: controller or target hosts are empty."
            self.taskFinished.emit(False, message)
            return False

        task_key = f"view-push-batch:{controller}:{module}"

        def run_batch(progress: Any) -> dict[str, Any]:
            """Run the bounded backend batch inside one coordinator task."""

            def host_changed(host: str, state: str, message: str, _value: int) -> None:
                """Relay only terminal host states through the stable Qt signal."""
                if state not in {"success", "error", "cancelled"}:
                    return
                self.viewPushFinished.emit(
                    controller, host, module, state == "success", message
                )

            def batch_progress(
                completed: int, success: int, failed: int, total: int
            ) -> None:
                """Convert numeric batch progress to the existing text contract."""
                progress(
                    f"Pushing {controller.upper()}: {completed}/{total} completed, "
                    f"{success} succeeded, {failed} failed."
                )

            return self._view_push_batch.run(
                controller,
                module,
                targets,
                on_host=host_changed,
                on_progress=batch_progress,
            )

        return self._start_background_task(
            task_key,
            controller,
            "",
            module,
            f"Pushing {controller.upper()} configuration to {len(targets)} devices...",
            run_batch,
            "batch",
        )

    @pyqtSlot(str, result="QVariant")
    def previewDhcpConfig(self, host: str) -> dict[str, Any]:
        """Provide the legacy DHCP preview wrapper used by QML."""
        return self.previewViewPush("dhcp", host, "all")

    @pyqtSlot(str, result="QVariant")
    def pushDhcpConfig(self, host: str) -> dict[str, Any]:
        """Provide the legacy DHCP push wrapper used by QML."""
        return self.pushViewPush("dhcp", host, "all")
