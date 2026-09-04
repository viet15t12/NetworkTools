"""Cross-platform ICMP probe and terminal-launch adapter."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from infrastructure.system.network_info import _decode_command_output

def _ping_probe_command(ip: str) -> list[str]:
    if os.name == "nt":
        return ["ping", "-n", "1", "-w", "1200", ip]
    if sys.platform == "darwin":
        return ["ping", "-c", "1", "-W", "1200", ip]
    return ["ping", "-c", "1", "-W", "2", ip]


def _last_non_empty_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def ping_host(app_dir: Path, ip: str) -> dict[str, Any]:
    probe_command = _ping_probe_command(ip)
    try:
        kwargs: dict[str, Any] = {
            "capture_output": True,
            "check": False,
            "timeout": 4,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(probe_command, **kwargs)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "severity": "error",
            "message": f"Ping failed for {ip}: request timed out.",
        }
    except OSError as exc:
        return {
            "ok": False,
            "severity": "error",
            "message": f"Ping failed for {ip}: could not start ping command ({exc}).",
        }

    output = _decode_command_output((result.stdout or b"") + (result.stderr or b""))
    if result.returncode != 0:
        detail = _last_non_empty_line(output)
        reason = detail or "host is unreachable or did not respond."
        return {
            "ok": False,
            "severity": "error",
            "message": f"Ping failed for {ip}: {reason}",
        }

    if os.name == "nt":
        try:
            subprocess.Popen(
                ["cmd.exe", "/k", "ping", ip],
                cwd=str(app_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as exc:
            return {
                "ok": False,
                "severity": "warning",
                "message": f"Ping succeeded for {ip}, but opening the ping terminal failed: {exc}",
            }
        return {
            "ok": True,
            "severity": "success",
            "message": f"Ping succeeded for {ip}; terminal ping opened.",
        }

    try:
        subprocess.Popen(["x-terminal-emulator", "-e", "ping", ip])
        return {
            "ok": True,
            "severity": "success",
            "message": f"Ping succeeded for {ip}; terminal ping opened.",
        }
    except OSError:
        try:
            subprocess.Popen(["ping", ip])
            return {
                "ok": True,
                "severity": "success",
                "message": f"Ping succeeded for {ip}; background ping started.",
            }
        except OSError as exc:
            return {
                "ok": False,
                "severity": "warning",
                "message": f"Ping succeeded for {ip}, but opening a ping terminal failed: {exc}",
            }
