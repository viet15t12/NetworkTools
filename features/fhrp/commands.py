"""Cisco IOS template rendering for FHRP tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"


def render_fhrp_commands(
    task: dict[str, Any], template_folder: str = "cisco_ios"
) -> list[str]:
    """Render a task to normalized CLI lines using the platform template."""
    folder = "cisco_ios" if template_folder in {"cisco", "cisco_ios_telnet"} else template_folder
    template_path = TEMPLATE_ROOT / folder / "fhrp.j2"
    if not template_path.exists():
        raise ValueError(f"FHRP template is not available for {template_folder}")
    environment = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=True,
        autoescape=False,
    )
    rendered = environment.get_template(template_path.name).render(
        config=task.get("config") or {},
        mode=str(task.get("action") or "setup").lower(),
    )
    return [
        line.strip()
        for line in rendered.splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]


def redact_fhrp_commands(lines: list[str]) -> list[str]:
    """Hide authentication material in previews and reports."""
    redacted: list[str] = []
    for line in lines:
        lower = line.lower()
        if " authentication " in f" {lower} ":
            parts = line.split()
            if parts:
                parts[-1] = "<redacted>"
                line = " ".join(parts)
        redacted.append(line)
    return redacted


def redact_fhrp_output(text: Any, task: dict[str, Any]) -> str:
    """Remove a task's authentication value from echoed Cisco CLI output."""
    output = str(text or "")
    secret = str(
        (task.get("config") or {}).get("options", {}).get("auth_secret") or ""
    )
    return output.replace(secret, "<redacted>") if secret else output
