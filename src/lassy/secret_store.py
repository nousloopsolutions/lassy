"""User-bound Windows DPAPI storage for the local runner credential."""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from pathlib import Path


CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class RunnerSecretStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "runner-secret.dpapi"

    def set(self, secret: str) -> str:
        if len(secret) < 32:
            raise ValueError("runner secret must be at least 32 characters")
        encrypted = _protect(secret.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_bytes(encrypted)
        os.chmod(temp, 0o600)
        temp.replace(self.path)
        return fingerprint(secret)

    def get(self) -> str:
        if not self.path.exists():
            raise FileNotFoundError("runner credential has not been initialized")
        return _unprotect(self.path.read_bytes()).decode("utf-8")

    def fingerprint(self) -> str | None:
        if not self.path.exists():
            return None
        return fingerprint(self.get())


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI credential storage is available only on Windows")
    return _crypt_protect(value)


def _unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI credential storage is available only on Windows")
    return _crypt_unprotect(value)


def _blob(value: bytes) -> tuple[DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    blob = DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _crypt_protect(value: bytes) -> bytes:
    source, source_buffer = _blob(value)
    destination = DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "LASSY runner credential",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError()
    del source_buffer
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


def _crypt_unprotect(value: bytes) -> bytes:
    source, source_buffer = _blob(value)
    destination = DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError()
    del source_buffer
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)
