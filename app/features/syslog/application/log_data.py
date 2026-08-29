"""Application service for exporting and destructively resetting Syslog data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..export import export_logs_xlsx


class LogDataRepository(Protocol):
    def reset_options(self) -> dict[str, Any]: ...

    def messages_for_export(self, host: str = "") -> list[dict[str, Any]]: ...

    def reset_messages(self, host: str = "") -> int: ...


def reset_confirmation_phrase(host: str) -> str:
    selected_host = str(host or "").strip()
    return f"DELETE {selected_host}" if selected_host else "DELETE ALL SYSLOG DATA"


class SyslogLogDataService:
    """Apply reset-scope, export-limit, and confirmation policy."""

    MAX_EXCEL_DATA_ROWS = 1_048_570

    def __init__(self, repository: LogDataRepository) -> None:
        self.repository = repository

    def options(self) -> dict[str, Any]:
        summary = self.repository.reset_options()
        options = [
            {
                "host": "",
                "label": f"All hosts ({summary['total']} messages)",
                "count": summary["total"],
            }
        ]
        options.extend(
            {
                "host": row["host"],
                "label": f"{row['host']} ({row['count']} messages)",
                "count": row["count"],
            }
            for row in summary["hosts"]
        )
        return {"ok": True, "total": summary["total"], "options": options}

    def is_authorized(self, host: str, confirmation: str) -> bool:
        return confirmation == reset_confirmation_phrase(host)

    def export_scope(self, target: Path, host: str) -> dict[str, Any]:
        selected_host = str(host or "").strip()
        values = self.repository.messages_for_export(selected_host)
        if not values:
            return {
                "ok": False,
                "message": "There are no logs in this scope to export.",
            }
        if len(values) > self.MAX_EXCEL_DATA_ROWS:
            return {
                "ok": False,
                "message": (
                    "This scope exceeds the Excel worksheet row limit. "
                    "Reset a smaller host scope."
                ),
            }
        exported = export_logs_xlsx(target, values, {"host": selected_host})
        return {
            "ok": True,
            "message": f"Exported {len(values)} logs to {exported}",
            "path": str(exported),
            "count": len(values),
        }

    def reset(self, host: str, confirmation: str) -> dict[str, Any]:
        selected_host = str(host or "").strip()
        expected = reset_confirmation_phrase(selected_host)
        if confirmation != expected:
            return {
                "ok": False,
                "deleted": 0,
                "message": f'Type "{expected}" exactly to authorize deletion.',
            }
        deleted = self.repository.reset_messages(selected_host)
        scope = selected_host if selected_host else "all hosts"
        return {
            "ok": True,
            "deleted": deleted,
            "message": f"Deleted {deleted} Syslog messages for {scope}.",
        }


__all__ = ["SyslogLogDataService", "reset_confirmation_phrase"]
