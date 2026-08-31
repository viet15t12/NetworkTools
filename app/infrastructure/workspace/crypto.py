"""Streaming authenticated encryption for protected ``.ntp`` packages.

The encrypted representation is deliberately not an encrypted ZIP variant.
It is a small, versioned CAMS envelope followed by AES-256-GCM
ciphertext.  Decryption recreates the exact ordinary ZIP payload used by an
unprotected project.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from .errors import (
    InvalidWorkspacePackage,
    UnsupportedWorkspaceVersion,
    WorkspaceAuthenticationError,
    WorkspacePasswordRequired,
)


ENVELOPE_MAGIC = b"NTPAES1\0"
ENVELOPE_VERSION = 1
_PREFIX = struct.Struct(">8sI")
_TAG_SIZE = 16
_MAX_HEADER_SIZE = 16 * 1024
_DEFAULT_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Argon2Parameters:
    """Per-package Argon2id cost parameters.

    Production defaults use 64 MiB and three iterations.  Tests may inject
    lower (but still bounded) costs without changing the serialized format.
    ``memory_cost_kib`` follows the API and envelope unit explicitly.
    """

    memory_cost_kib: int = 64 * 1024
    iterations: int = 3
    lanes: int = 4

    def validate(self) -> None:
        if not 8 * 1024 <= self.memory_cost_kib <= 256 * 1024:
            raise InvalidWorkspacePackage("Unsupported Argon2id memory cost.")
        if not 1 <= self.iterations <= 6:
            raise InvalidWorkspacePackage("Unsupported Argon2id iteration count.")
        if not 1 <= self.lanes <= 8:
            raise InvalidWorkspacePackage("Unsupported Argon2id lane count.")


def is_encrypted_package(path: str | Path) -> bool:
    """Return whether *path* starts with the protected-project magic."""

    package_path = Path(path)
    with package_path.open("rb") as stream:
        return stream.read(len(ENVELOPE_MAGIC)) == ENVELOPE_MAGIC


def encrypt_zip_payload(
    source: str | Path,
    destination: str | Path,
    password: str,
    *,
    parameters: Argon2Parameters | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> None:
    """Encrypt one ZIP payload to a new authenticated envelope."""

    if not password:
        raise ValueError("A non-empty password is required for encryption.")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    source_path = Path(source)
    destination_path = Path(destination)
    costs = parameters or Argon2Parameters()
    costs.validate()
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = {
        "cipher": "AES-256-GCM",
        "ciphertextLength": source_path.stat().st_size,
        "envelopeVersion": ENVELOPE_VERSION,
        "format": "networktools-encrypted-project",
        "kdf": "Argon2id",
        "kdfParameters": {
            "iterations": costs.iterations,
            "lanes": costs.lanes,
            "memoryCostKiB": costs.memory_cost_kib,
        },
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "tagLength": _TAG_SIZE,
    }
    header_bytes = json.dumps(
        header, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    prefix = _PREFIX.pack(ENVELOPE_MAGIC, len(header_bytes))
    authenticated_header = prefix + header_bytes

    key = bytearray(_derive_key(password, salt, costs))
    try:
        encryptor = Cipher(algorithms.AES(bytes(key)), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(authenticated_header)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as plain, destination_path.open("wb") as protected:
            protected.write(authenticated_header)
            _transform_stream(plain, protected, encryptor, chunk_size)
            protected.write(encryptor.finalize())
            protected.write(encryptor.tag)
            protected.flush()
            os.fsync(protected.fileno())
    finally:
        _clear(key)


def decrypt_zip_payload(
    source: str | Path,
    destination: str | Path,
    password: str | None,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> None:
    """Authenticate and decrypt an envelope without exposing partial output."""

    if not password:
        raise WorkspacePasswordRequired("This project is password protected.")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    source_path = Path(source)
    destination_path = Path(destination)
    partial_path: Path | None = None
    key: bytearray | None = None
    try:
        with source_path.open("rb") as protected:
            header, authenticated_header, ciphertext_length, tag = _read_envelope(
                protected, source_path.stat().st_size
            )
            costs = _parse_costs(header)
            salt = _decode_fixed(header, "salt", 16)
            nonce = _decode_fixed(header, "nonce", 12)
            key = bytearray(_derive_key(password, salt, costs))
            decryptor = Cipher(
                algorithms.AES(bytes(key)), modes.GCM(nonce, tag)
            ).decryptor()
            decryptor.authenticate_additional_data(authenticated_header)

            destination_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, partial_name = tempfile.mkstemp(
                prefix=destination_path.name + ".",
                suffix=".partial",
                dir=destination_path.parent,
            )
            partial_path = Path(partial_name)
            with os.fdopen(descriptor, "wb") as plain:
                _transform_stream(
                    protected,
                    plain,
                    decryptor,
                    chunk_size,
                    byte_limit=ciphertext_length,
                )
                plain.write(decryptor.finalize())
                plain.flush()
                os.fsync(plain.fileno())
        os.replace(partial_path, destination_path)
    except (WorkspacePasswordRequired, UnsupportedWorkspaceVersion):
        raise
    except (
        InvalidWorkspacePackage,
        InvalidTag,
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise WorkspaceAuthenticationError(
            "Unable to unlock this project. The password is incorrect or the file is damaged."
        ) from exc
    finally:
        if partial_path is not None:
            partial_path.unlink(missing_ok=True)
        if key is not None:
            _clear(key)


def _read_envelope(
    stream: BinaryIO, total_size: int
) -> tuple[dict[str, object], bytes, int, bytes]:
    prefix = stream.read(_PREFIX.size)
    if len(prefix) != _PREFIX.size:
        raise InvalidWorkspacePackage("The encrypted project header is truncated.")
    magic, header_size = _PREFIX.unpack(prefix)
    if magic != ENVELOPE_MAGIC:
        raise InvalidWorkspacePackage("Not a CAMS encrypted project.")
    if not 1 <= header_size <= _MAX_HEADER_SIZE:
        raise InvalidWorkspacePackage("The encrypted project header is invalid.")
    header_bytes = stream.read(header_size)
    if len(header_bytes) != header_size:
        raise InvalidWorkspacePackage("The encrypted project header is truncated.")
    header = json.loads(header_bytes.decode("utf-8"))
    if not isinstance(header, dict):
        raise InvalidWorkspacePackage("The encrypted project header is invalid.")
    if header.get("format") != "networktools-encrypted-project":
        raise InvalidWorkspacePackage("Unknown encrypted project format.")
    envelope_version = header.get("envelopeVersion")
    if isinstance(envelope_version, bool) or envelope_version != ENVELOPE_VERSION:
        raise UnsupportedWorkspaceVersion("Unsupported encrypted project version.")
    if header.get("cipher") != "AES-256-GCM" or header.get("kdf") != "Argon2id":
        raise UnsupportedWorkspaceVersion("Unsupported project encryption algorithm.")
    if header.get("tagLength") != _TAG_SIZE:
        raise InvalidWorkspacePackage("The encrypted project tag length is invalid.")

    ciphertext_length = header.get("ciphertextLength")
    if (
        isinstance(ciphertext_length, bool)
        or not isinstance(ciphertext_length, int)
        or ciphertext_length < 0
    ):
        raise InvalidWorkspacePackage("The encrypted payload length is invalid.")
    expected_size = _PREFIX.size + header_size + ciphertext_length + _TAG_SIZE
    if total_size != expected_size:
        raise InvalidWorkspacePackage("The encrypted project length is inconsistent.")

    tag_offset = total_size - _TAG_SIZE
    stream.seek(tag_offset)
    tag = stream.read(_TAG_SIZE)
    stream.seek(_PREFIX.size + header_size)
    return header, prefix + header_bytes, ciphertext_length, tag


def _parse_costs(header: dict[str, object]) -> Argon2Parameters:
    raw = header.get("kdfParameters")
    if not isinstance(raw, dict):
        raise InvalidWorkspacePackage("The Argon2id parameters are missing.")
    costs = Argon2Parameters(
        memory_cost_kib=_strict_int(raw, "memoryCostKiB"),
        iterations=_strict_int(raw, "iterations"),
        lanes=_strict_int(raw, "lanes"),
    )
    costs.validate()
    return costs


def _strict_int(values: dict[object, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidWorkspacePackage(f"Invalid encrypted header field: {key}.")
    return value


def _decode_fixed(header: dict[str, object], key: str, length: int) -> bytes:
    value = header.get(key)
    if not isinstance(value, str):
        raise InvalidWorkspacePackage(f"Missing encrypted header field: {key}.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InvalidWorkspacePackage(f"Invalid encrypted header field: {key}.") from exc
    if len(decoded) != length:
        raise InvalidWorkspacePackage(f"Invalid encrypted header field: {key}.")
    return decoded


def _derive_key(password: str, salt: bytes, costs: Argon2Parameters) -> bytes:
    password_bytes = bytearray(password.encode("utf-8"))
    try:
        return Argon2id(
            salt=salt,
            length=32,
            iterations=costs.iterations,
            lanes=costs.lanes,
            memory_cost=costs.memory_cost_kib,
        ).derive(bytes(password_bytes))
    finally:
        _clear(password_bytes)


def _transform_stream(
    source: BinaryIO,
    destination: BinaryIO,
    transform: object,
    chunk_size: int,
    *,
    byte_limit: int | None = None,
) -> None:
    remaining = byte_limit
    while remaining is None or remaining > 0:
        requested = chunk_size if remaining is None else min(chunk_size, remaining)
        chunk = source.read(requested)
        if not chunk:
            if remaining is not None:
                raise InvalidWorkspacePackage("The encrypted payload is truncated.")
            break
        destination.write(transform.update(chunk))  # type: ignore[attr-defined]
        if remaining is not None:
            remaining -= len(chunk)


def _clear(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


__all__ = [
    "Argon2Parameters",
    "ENVELOPE_MAGIC",
    "decrypt_zip_payload",
    "encrypt_zip_payload",
    "is_encrypted_package",
]
