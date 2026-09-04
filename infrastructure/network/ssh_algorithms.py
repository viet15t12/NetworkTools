"""Validated, per-connection SSH algorithm preferences."""

from __future__ import annotations

from dataclasses import dataclass
import platform
from typing import Any, Iterable

import paramiko
import netmiko


class UnsupportedSshAlgorithm(ValueError):
    """Raised before socket negotiation when an override is unsupported."""

    code = "UNSUPPORTED_ALGORITHM"


@dataclass(frozen=True)
class SshAlgorithmOverride:
    kex: tuple[str, ...] = ()
    key_types: tuple[str, ...] = ()
    ciphers: tuple[str, ...] = ()
    digests: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return any((self.kex, self.key_types, self.ciphers, self.digests))


def normalize_algorithm_list(value: Any) -> tuple[str, ...]:
    """Normalize CSV/iterable values, preserving the user's preference order."""
    if value is None:
        return ()
    items = value.split(",") if isinstance(value, str) else value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item or "").strip()
        if name and name not in seen:
            normalized.append(name)
            seen.add(name)
    return tuple(normalized)


def merge_preferred(overrides: Iterable[str], defaults: Iterable[str]) -> tuple[str, ...]:
    return normalize_algorithm_list((*overrides, *defaults))


def _supported_algorithms() -> dict[str, set[str]]:
    """Keep Paramiko compatibility details isolated in this adapter."""
    transport = paramiko.Transport
    return {
        "kex": set(getattr(transport, "_kex_info", {})),
        "key_types": set(getattr(transport, "_key_info", {})),
        "ciphers": set(getattr(transport, "_cipher_info", {})),
        "digests": set(getattr(transport, "_mac_info", {})),
    }


def validate_override(override: SshAlgorithmOverride) -> None:
    supported = _supported_algorithms()
    for group in ("kex", "key_types", "ciphers", "digests"):
        unknown = [name for name in getattr(override, group) if name not in supported[group]]
        if unknown:
            raise UnsupportedSshAlgorithm(
                f"UNSUPPORTED_ALGORITHM: unsupported SSH {group}: {', '.join(unknown)}"
            )


def make_transport_factory(override: SshAlgorithmOverride):
    """Return a Paramiko transport factory that never mutates class-level state."""
    validate_override(override)

    def factory(sock: Any, **kwargs: Any) -> paramiko.Transport:
        transport = paramiko.Transport(sock, **kwargs)
        options = transport.get_security_options()
        options.kex = merge_preferred(override.kex, options.kex)
        options.key_types = merge_preferred(override.key_types, options.key_types)
        options.ciphers = merge_preferred(override.ciphers, options.ciphers)
        options.digests = merge_preferred(override.digests, options.digests)
        return transport

    return factory


def classify_ssh_error(exc: BaseException) -> str:
    """Map negotiation failures to stable diagnostic codes without secrets."""
    if isinstance(exc, UnsupportedSshAlgorithm):
        return exc.code
    text = str(exc or "").lower()
    patterns = (
        ("unsupported_algorithm", "UNSUPPORTED_ALGORITHM"),
        ("no_matching_kex", "NO_MATCHING_KEX"),
        ("no_matching_host_key", "NO_MATCHING_HOST_KEY"),
        ("no_matching_cipher", "NO_MATCHING_CIPHER"),
        ("no_matching_mac", "NO_MATCHING_MAC"),
        ("no acceptable kex", "NO_MATCHING_KEX"),
        ("no acceptable host key", "NO_MATCHING_HOST_KEY"),
        ("no acceptable cipher", "NO_MATCHING_CIPHER"),
        ("no acceptable ciphers", "NO_MATCHING_CIPHER"),
        ("no acceptable mac", "NO_MATCHING_MAC"),
        ("no acceptable macs", "NO_MATCHING_MAC"),
        ("cryptography", "CRYPTO_BACKEND_REJECTED"),
        ("authentication", "AUTHENTICATION_FAILED"),
        ("timed out", "CONNECTION_TIMEOUT"),
        ("timeout", "CONNECTION_TIMEOUT"),
    )
    for marker, code in patterns:
        if marker in text:
            return code
    return "CONNECTION_ERROR"


def ssh_runtime_diagnostics(
    code: str = "OK", message: str = ""
) -> dict[str, str]:
    """Return safe runtime/version context without credentials or secrets."""
    return {
        "code": str(code or "CONNECTION_ERROR"),
        "message": str(message or ""),
        "python": platform.python_version(),
        "paramiko": str(paramiko.__version__),
        "netmiko": str(netmiko.__version__),
    }
