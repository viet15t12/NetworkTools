from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

from PyQt6.QtCore import QSettings


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DpapiCredentialStore:
    """Current-user Windows DPAPI storage backed by the application settings."""

    _PREFIX = "SFTP/credentials/"
    _ENTROPY = b"CAMS:SFTP:v1"
    _UI_FORBIDDEN = 0x1

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings
        self._crypt32 = None
        self._kernel32 = None
        if os.name != "nt":
            return
        try:
            crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
            kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
            crypt32.CryptProtectData.argtypes = [
                ctypes.POINTER(_DataBlob),
                wintypes.LPCWSTR,
                ctypes.POINTER(_DataBlob),
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(_DataBlob),
            ]
            crypt32.CryptProtectData.restype = wintypes.BOOL
            crypt32.CryptUnprotectData.argtypes = [
                ctypes.POINTER(_DataBlob),
                ctypes.c_void_p,
                ctypes.POINTER(_DataBlob),
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(_DataBlob),
            ]
            crypt32.CryptUnprotectData.restype = wintypes.BOOL
            kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            kernel32.LocalFree.restype = ctypes.c_void_p
            self._crypt32 = crypt32
            self._kernel32 = kernel32
        except (AttributeError, OSError):
            self._crypt32 = None
            self._kernel32 = None

    @property
    def available(self) -> bool:
        return self._crypt32 is not None and self._kernel32 is not None

    @staticmethod
    def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
        buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
        return (
            _DataBlob(
                len(value),
                ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            ),
            buffer,
        )

    def _transform(self, value: bytes, *, protect: bool) -> bytes:
        if not self.available:
            raise RuntimeError("Windows credential protection is unavailable")
        input_blob, input_buffer = self._blob(value)
        entropy_blob, entropy_buffer = self._blob(self._ENTROPY)
        output_blob = _DataBlob()
        function = (
            self._crypt32.CryptProtectData
            if protect
            else self._crypt32.CryptUnprotectData
        )
        description = "CAMS SFTP credential" if protect else None
        if not function(
            ctypes.byref(input_blob),
            description,
            ctypes.byref(entropy_blob),
            None,
            None,
            self._UI_FORBIDDEN,
            ctypes.byref(output_blob),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            self._kernel32.LocalFree(
                ctypes.cast(output_blob.pbData, ctypes.c_void_p)
            )
            del input_buffer, entropy_buffer

    def has(self, profile_id: str) -> bool:
        return bool(str(self._settings.value(self._PREFIX + profile_id, "") or ""))

    def read(self, profile_id: str) -> str:
        encoded = str(self._settings.value(self._PREFIX + profile_id, "") or "")
        if not encoded:
            return ""
        try:
            protected = base64.b64decode(encoded.encode("ascii"), validate=True)
            return self._transform(protected, protect=False).decode("utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            return ""

    def write(self, profile_id: str, password: str) -> None:
        if not password:
            self.delete(profile_id)
            return
        protected = self._transform(password.encode("utf-8"), protect=True)
        self._settings.setValue(
            self._PREFIX + profile_id,
            base64.b64encode(protected).decode("ascii"),
        )
        self._settings.sync()

    def delete(self, profile_id: str) -> None:
        self._settings.remove(self._PREFIX + profile_id)
        self._settings.sync()

