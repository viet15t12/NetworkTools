"""Prompt-delimited Cisco running-configuration collection."""

from __future__ import annotations

import re
import time
from typing import Any


CONFIG_PROMPT_RE = re.compile(r"(?m)^[^\r\n]*\(config(?:-[^)]+)?\)#[ \t]*$")
PRIVILEGED_PROMPT_RE = re.compile(r"(?m)^[^\r\n]*#[ \t]*$")
PROMPT_NOISE_RE = re.compile(r"(?:\x00|\^@)+")


class RunningConfigCollector:
    """Read CLI chunks until the configuration prompt is received in full."""

    def __init__(
        self,
        connection: Any,
        *,
        read_timeout: float = 15.0,
        poll_interval: float = 0.02,
    ) -> None:
        self.connection = connection
        self.read_timeout = max(0.1, float(read_timeout))
        self.poll_interval = max(0.0, float(poll_interval))

    def collect(self) -> str:
        prompt = self._ensure_privileged_prompt()
        prefix = "do " if CONFIG_PROMPT_RE.fullmatch(prompt) else ""
        paging_command = f"{prefix}terminal length 0"
        collect_command = f"{prefix}show running-config"
        self._send_and_wait_for_prompt(paging_command, prompt)
        output = self._send_and_wait_for_prompt(collect_command, prompt)
        return self._clean_output(output, collect_command, prompt)

    def _ensure_privileged_prompt(self) -> str:
        """Use the current privileged mode without forcing configuration mode."""
        prompt = self._clean_prompt(self.connection.find_prompt())
        if PRIVILEGED_PROMPT_RE.fullmatch(prompt):
            return prompt
        if hasattr(self.connection, "check_enable_mode") and not self.connection.check_enable_mode():
            self.connection.enable()
            prompt = self._clean_prompt(self.connection.find_prompt())
        if not PRIVILEGED_PROMPT_RE.fullmatch(prompt):
            raise RuntimeError(
                f"Expected a privileged Cisco prompt, received: {prompt or '<empty>'}"
            )
        return prompt

    def _send_and_wait_for_prompt(self, command: str, prompt: str) -> str:
        self.connection.clear_buffer()
        self.connection.write_channel(command + self.connection.RETURN)
        chunks: list[str] = []
        deadline = time.monotonic() + self.read_timeout
        while True:
            chunk = self.connection.read_channel()
            if chunk:
                chunks.append(str(chunk))
                buffer = "".join(chunks).replace("\r\n", "\n").replace("\r", "\n")
                if self._ends_with_prompt(buffer, prompt):
                    return buffer
            elif hasattr(self.connection, "is_alive"):
                state = self.connection.is_alive()
                if isinstance(state, dict) and not bool(state.get("is_alive")):
                    raise ConnectionError("Device connection closed before the configuration prompt returned")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out after {self.read_timeout:g}s waiting for the prompt "
                    f"after: {command}"
                )
            if not chunk and self.poll_interval:
                time.sleep(self.poll_interval)

    @staticmethod
    def _clean_prompt(value: Any) -> str:
        return PROMPT_NOISE_RE.sub("", str(value or "")).strip()

    @classmethod
    def _ends_with_prompt(cls, output: str, prompt: str) -> bool:
        lines = str(output or "").split("\n")
        last_line = next((line for line in reversed(lines) if line.strip()), "")
        return cls._clean_prompt(last_line) == cls._clean_prompt(prompt)

    @classmethod
    def _clean_output(cls, output: str, command: str, prompt: str) -> str:
        lines = str(output or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if lines and lines[0].strip() == command:
            lines.pop(0)
        clean_prompt = cls._clean_prompt(prompt)
        # The full output is already on the application host at this point.
        # Remove every repeated trailing prompt (including NUL/^@ noise) and
        # surrounding blank lines locally. Cisco config delimiters such as
        # standalone "!" and "end" lines are part of the saved snapshot.
        while lines and (
            not lines[-1].strip()
            or cls._clean_prompt(lines[-1]) == clean_prompt
        ):
            lines.pop()
        return "\n".join(lines).strip("\n") + "\n"
