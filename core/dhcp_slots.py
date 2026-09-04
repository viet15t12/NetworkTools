from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSlot

from features.dhcp import (
    add_dhcp_helper_address,
    add_dhcp_pool,
    add_excluded_address,
    delete_dhcp_helper_address,
    delete_dhcp_pool,
    delete_excluded_address,
    get_dhcp_helper_addresses,
    get_dhcp_pools,
    get_excluded_addresses,
    update_dhcp_pool,
)


def _load_network_dhcp_module(app_dir: Path, module_name: str):
    if module_name == "main":
        from features.dhcp import dispatcher
        return dispatcher
    if module_name == "worker_dhcp":
        from features.dhcp import worker
        return worker
    raise ImportError(f"Unknown DHCP module: {module_name}")


class DhcpSlotsMixin:
    @pyqtSlot(str, result="QVariant")
    def getDhcpPools(self, host: str) -> list[dict[str, Any]]:
        return get_dhcp_pools(self, host)

    @pyqtSlot(str, str, str, str, str, str, str, result=bool)
    def addDhcpPool(self, host: str, pool: str, network: str, subnetmask: str, default: str, dns: str, lease: str) -> bool:
        return add_dhcp_pool(self, host, pool, network, subnetmask, default, dns, lease)

    @pyqtSlot(int, str, str, str, str, str, str, result=bool)
    def updateDhcpPool(self, dhcp_id: int, pool: str, network: str, subnetmask: str, default: str, dns: str, lease: str) -> bool:
        return update_dhcp_pool(self, dhcp_id, pool, network, subnetmask, default, dns, lease)

    @pyqtSlot(int, result=bool)
    def deleteDhcpPool(self, dhcp_id: int) -> bool:
        return delete_dhcp_pool(self, dhcp_id)

    @pyqtSlot(str, result="QVariant")
    def getExcludedAddresses(self, host: str) -> list[dict[str, Any]]:
        return get_excluded_addresses(self, host)

    @pyqtSlot(str, str, str, result=bool)
    def addExcludedAddress(self, host: str, start_ip: str, end_ip: str) -> bool:
        return add_excluded_address(self, host, start_ip, end_ip)

    @pyqtSlot(int, result=bool)
    def deleteExcludedAddress(self, ex_id: int) -> bool:
        return delete_excluded_address(self, ex_id)

    @pyqtSlot(str, result="QVariant")
    def getDhcpHelperAddresses(self, host: str) -> list[dict[str, Any]]:
        return get_dhcp_helper_addresses(self, host)

    @pyqtSlot(int, str, result=bool)
    def addDhcpHelperAddress(self, iface_id: int, helper_ip: str) -> bool:
        return add_dhcp_helper_address(self, iface_id, helper_ip)

    @pyqtSlot(int, result=bool)
    def deleteDhcpHelperAddress(self, helper_id: int) -> bool:
        return delete_dhcp_helper_address(self, helper_id)

    @pyqtSlot(str, result="QVariant")
    def previewDhcpConfig(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        if not host:
            return {"ok": False, "message": "Host is empty.", "commands": "", "tasks": []}
        try:
            self._sync_worker_paths()
            dhcp_main = _load_network_dhcp_module(self.app_dir, "main")
            dhcp_worker = _load_network_dhcp_module(self.app_dir, "worker_dhcp")

            tasks = dhcp_main.dhcp_dispatcher(target_ip=host, dry_run=True) or []
            if not tasks:
                return {"ok": True, "message": "No pending DHCP configuration to push.", "commands": "", "tasks": []}

            rendered: list[str] = []
            for task in tasks:
                target = task.get("target", {}).get("ip", host)
                context = self._routing_device_context(target)
                rendered.append(f"# {target} / DHCP / {str(task.get('action') or 'setup').upper()}")
                commands = dhcp_worker.render_dhcp_template(context["template_folder"], task)
                lines = [line.strip() for line in commands.splitlines() if line.strip() and not line.strip().startswith("!")]
                rendered.extend(lines or ["# No commands rendered."])
                rendered.append("")

            return {"ok": True, "message": f"Prepared {len(tasks)} DHCP task(s).", "commands": "\n".join(rendered).strip(), "tasks": tasks}
        except Exception as exc:
            message = f"Preview DHCP failed: {exc}"
            print(f"[db] {message}", file=sys.stderr)
            return {"ok": False, "message": message, "commands": "", "tasks": []}

    @pyqtSlot(str, result="QVariant")
    def pushDhcpConfig(self, host: str) -> dict[str, Any]:
        host = (host or "").strip()
        if not host:
            return {"ok": False, "message": "Host is empty.", "report": []}
        try:
            self._sync_worker_paths()
            from infrastructure.network.config import DHCP_OUTPUT
            dhcp_main = _load_network_dhcp_module(self.app_dir, "main")

            tasks = dhcp_main.dhcp_dispatcher(target_ip=host, dry_run=False) or []
            if not tasks:
                return {"ok": True, "message": "No pending DHCP configuration to push.", "report": []}

            log_path = Path(DHCP_OUTPUT)
            report: list[dict[str, Any]] = []
            if log_path.exists():
                report = json.loads(log_path.read_text(encoding="utf-8"))

            ok = bool(report) and all(str(item.get("status", "")).lower() == "success" for item in report)
            return {"ok": ok, "message": "DHCP push completed." if ok else "DHCP push finished with errors.", "report": report}
        except Exception as exc:
            message = f"Push DHCP failed: {exc}"
            print(f"[db] {message}", file=sys.stderr)
            return {"ok": False, "message": message, "report": []}
