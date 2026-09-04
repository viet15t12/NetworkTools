"""Coordinate Cisco validation, worker I/O, verification, and persisted state."""

from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

from .commands import build_cancel_commands, build_enable_commands
from .verifier import verify_destination, verify_source_interface
from .worker import CiscoSyslogWorker


SUPPORTED_DEVICE_OS = {"ios", "ios_xe", "cisco_ios", "cisco_xe"}
logger = logging.getLogger(__name__)


class ConfigRepository(Protocol):
    def is_connected(self, host: str) -> bool: ...
    def device_os(self, host: str) -> str: ...
    def source_interface(self, host: str) -> str | None: ...
    def save_device_state(self, *args: object) -> None: ...


class SyslogConfigurator:
    def __init__(self, repository: ConfigRepository, session_registry: Any | None = None) -> None:
        self.repository = repository
        self._session_registry = session_registry

    def configure(
        self, host: str, server_ip: str, protocol: str, port: int,
        source_interface: str = "", trap_severity: int = 5,
        timestamps: bool = False, sequence_numbers: bool = False,
    ) -> dict[str, object]:
        validation = self._validate_host(host)
        if validation is not None:
            return validation
        try:
            interface = source_interface.strip() or self.repository.source_interface(host)
        except Exception as exc:
            return self._database_read_failure(host, "source interface", exc)
        if not interface:
            return {
                "ok": False, "code": "source_interface_required", "stage": "validate",
                "message": (
                    f"Interface data for {host} is not synchronized. "
                    "Enter the Cisco source interface manually."
                ),
            }
        try:
            commands = build_enable_commands(
                server_ip, protocol, port, interface, trap_severity,
                timestamps, sequence_numbers,
            )
        except (TypeError, ValueError) as exc:
            return {"ok": False, "stage": "validate", "message": str(exc)}
        result = self._run_transaction(
            host,
            lambda connector: self._configure_transaction(
                host, CiscoSyslogWorker(connector), commands,
                server_ip, protocol, port, interface,
            ),
        )
        try:
            self.repository.save_device_state(
                host, server_ip, protocol, port, interface,
                bool(result["ok"]), str(result["message"]),
                trap_severity, timestamps, sequence_numbers,
            )
        except Exception as exc:
            return self._database_failure(host, result, exc)
        return result

    def cancel(self, host: str, server_ip: str, protocol: str, port: int) -> dict[str, object]:
        validation = self._validate_host(host)
        if validation is not None:
            return validation
        try:
            commands = build_cancel_commands(server_ip, protocol, port)
        except (TypeError, ValueError) as exc:
            return {"ok": False, "stage": "validate", "message": str(exc)}
        result = self._run_transaction(
            host,
            lambda connector: self._cancel_transaction(
                host, CiscoSyslogWorker(connector), commands, server_ip, protocol, port
            ),
        )
        try:
            if result["ok"]:
                self.repository.save_device_state(
                    host, server_ip, protocol, port, None, False, str(result["message"])
                )
            else:
                record_attempt = getattr(self.repository, "save_device_attempt", None)
                if callable(record_attempt):
                    record_attempt(host, server_ip, protocol, port, str(result["message"]))
        except Exception as exc:
            return self._database_failure(host, result, exc)
        return result

    def _validate_host(self, host: str) -> dict[str, object] | None:
        try:
            connected = self.repository.is_connected(host)
            device_os = self.repository.device_os(host).replace("-", "_").replace(" ", "_")
        except Exception as exc:
            return self._database_read_failure(host, "device metadata", exc)
        if not connected:
            return {"ok": False, "stage": "validate", "message": f"{host} is not connected."}
        if device_os not in SUPPORTED_DEVICE_OS:
            return {
                "ok": False, "stage": "validate",
                "message": f"Syslog configuration does not support OS '{device_os or 'unknown'}'.",
            }
        return None

    def _registry(self) -> Any:
        if self._session_registry is None:
            from core.sessions import device_session_registry
            self._session_registry = device_session_registry
        return self._session_registry

    def _run_transaction(
        self, host: str, operation: Callable[[Any], dict[str, object]]
    ) -> dict[str, object]:
        try:
            execution = self._registry().execute(host, operation, ensure_open=True)
        except Exception as exc:
            message = f"Could not execute the Syslog transaction for {host}: {exc}"
            logger.exception("Syslog session execution failed for %s", host)
            return {"ok": False, "stage": "session", "message": message}
        if not bool(execution.get("ok")):
            message = str(execution.get("message") or f"No CLI session for {host}.")
            logger.error("Syslog session failure for %s: %s", host, message)
            return {"ok": False, "stage": "session", "message": message}
        value = execution.get("value")
        if not isinstance(value, dict):
            message = f"Syslog transaction for {host} returned no result."
            logger.error(message)
            return {"ok": False, "stage": "internal", "message": message}
        return value

    def _configure_transaction(
        self, host: str, worker: CiscoSyslogWorker, commands: list[str],
        server_ip: str, protocol: str, port: int, interface: str,
    ) -> dict[str, object]:
        try:
            if not worker.interface_exists(interface):
                return self._failure(
                    host, "interface", f"Source interface '{interface}' does not exist on {host}."
                )
        except Exception as exc:
            return self._failure(host, "interface", f"Could not validate source interface on {host}: {exc}")
        try:
            apply_output = worker.send(commands)
        except Exception as exc:
            return self._failure(host, "apply", f"Syslog apply failed for {host}: {exc}")
        failure = self._verify_config(host, worker, server_ip, protocol, port, interface, startup=False)
        if failure is not None:
            return failure
        try:
            save_output = worker.save()
        except Exception as exc:
            return self._failure(host, "save", f"copy running-config startup-config failed for {host}: {exc}")
        failure = self._verify_config(host, worker, server_ip, protocol, port, interface, startup=True)
        if failure is not None:
            return failure
        message = f"Syslog configuration applied, verified, and saved on {host}."
        logger.info(message)
        return {"ok": True, "stage": "complete", "message": message,
                "apply_output": apply_output, "save_output": save_output}

    def _cancel_transaction(
        self, host: str, worker: CiscoSyslogWorker, commands: list[str],
        server_ip: str, protocol: str, port: int,
    ) -> dict[str, object]:
        try:
            apply_output = worker.send(commands)
        except Exception as exc:
            return self._failure(host, "apply", f"Syslog cancellation failed for {host}: {exc}")
        failure = self._verify_absent(host, worker, server_ip, protocol, port, startup=False)
        if failure is not None:
            return failure
        try:
            save_output = worker.save()
        except Exception as exc:
            return self._failure(host, "save", f"copy running-config startup-config failed for {host}: {exc}")
        failure = self._verify_absent(host, worker, server_ip, protocol, port, startup=True)
        if failure is not None:
            return failure
        message = f"Syslog destination removed, verified, and saved on {host}."
        logger.info(message)
        return {"ok": True, "stage": "complete", "message": message,
                "apply_output": apply_output, "save_output": save_output}

    def _verify_config(
        self, host: str, worker: CiscoSyslogWorker, server_ip: str,
        protocol: str, port: int, interface: str, *, startup: bool,
    ) -> dict[str, object] | None:
        stage = "verify_startup" if startup else "verify_running"
        label = "Startup-config" if startup else "Running-config"
        try:
            output = worker.show_logging(startup=startup)
            message = verify_destination(output, server_ip, protocol, port, expected=True)
            if message:
                return self._failure(host, stage, message)
            if not verify_source_interface(output, interface):
                return self._failure(
                    host, stage,
                    f"{label} on {host} does not contain logging source-interface {interface}.",
                )
        except Exception as exc:
            prefix = f"Could not verify {label.lower()}" if not startup else "Startup-config verification failed"
            return self._failure(host, stage, f"{prefix} for {host}: {exc}")
        return None

    def _verify_absent(
        self, host: str, worker: CiscoSyslogWorker, server_ip: str,
        protocol: str, port: int, *, startup: bool,
    ) -> dict[str, object] | None:
        stage = "verify_startup" if startup else "verify_running"
        try:
            output = worker.show_logging(startup=startup)
            message = verify_destination(output, server_ip, protocol, port, expected=False)
            return self._failure(host, stage, message) if message else None
        except Exception as exc:
            label = "Startup-config" if startup else "Running-config"
            return self._failure(host, stage, f"{label} verification failed for {host}: {exc}")

    @staticmethod
    def _failure(host: str, stage: str, message: str) -> dict[str, object]:
        logger.warning("Syslog transaction failed for %s at %s: %s", host, stage, message)
        return {"ok": False, "stage": stage, "message": message}

    @staticmethod
    def _database_failure(
        host: str, prior_result: dict[str, object], exc: Exception,
    ) -> dict[str, object]:
        message = (
            f"{prior_result.get('message', 'Syslog device operation finished')} "
            f"Database state update failed for {host}: {exc}"
        )
        logger.exception("Syslog database state update failed for %s", host)
        return {**prior_result, "ok": False, "stage": "database", "message": message}

    @staticmethod
    def _database_read_failure(host: str, data_name: str, exc: Exception) -> dict[str, object]:
        message = f"Could not read Syslog {data_name} for {host} from the database: {exc}"
        logger.exception("Syslog database read failed for %s", host)
        return {"ok": False, "stage": "database", "message": message}


__all__ = ["SyslogConfigurator"]
