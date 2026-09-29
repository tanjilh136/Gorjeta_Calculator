"""Install key verification and machine binding.

* The build embeds only a PBKDF2-HMAC-SHA256 hash of the secret key (build_config.py).
* On activation the app writes %PROGRAMDATA%\\MistuGorjetas\\activation.dat containing
  the machine ID (hash of Windows MachineGuid + system drive volume serial).
* The record is encrypted with Windows DPAPI in machine scope, so it cannot even be
  decrypted on another PC; on top of that the machine ID is re-computed and compared
  on every launch.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime
from enum import Enum

from . import build_config, paths

log = logging.getLogger(__name__)

RECORD_MAGIC = b"MGACT1\n"
_ENTROPY = b"MistuGorjetas/activation/v1"


# ------------------------------------------------------------------ hashing
def pbkdf2_hex(key: str, salt_hex: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", key.encode("utf-8"), bytes.fromhex(salt_hex), iterations
    ).hex()


def installer_hash_hex(key: str, salt: str, iterations: int) -> str:
    """Iterated salted SHA-256, mirrored by the Pascal code in the Inno Setup script
    (which has SHA-256 but no HMAC): h = sha256(salt + key); then h = sha256(salt + h)."""
    h = hashlib.sha256((salt + key).encode("ascii")).hexdigest()
    for _ in range(iterations - 1):
        h = hashlib.sha256((salt + h).encode("ascii")).hexdigest()
    return h


def is_configured() -> bool:
    return bool(build_config.KEY_HASH and build_config.KEY_SALT and build_config.KEY_ITERATIONS)


def verify_key(key: str) -> bool:
    if not is_configured():
        return False
    key = key.strip()
    if not key:
        return False
    candidate = pbkdf2_hex(key, build_config.KEY_SALT, build_config.KEY_ITERATIONS)
    return hmac.compare_digest(candidate, build_config.KEY_HASH)


def key_fingerprint() -> str:
    """Identifies the key configured in this build (a new key forces re-activation)."""
    return hashlib.sha256(("fp:" + build_config.KEY_HASH).encode()).hexdigest()[:24]


# --------------------------------------------------------------- machine ID
def _windows_machine_guid() -> str:
    import winreg

    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, access
    ) as k:
        value, _ = winreg.QueryValueEx(k, "MachineGuid")
    return str(value).strip().lower()


def _windows_volume_serial() -> str:
    import ctypes
    from ctypes import wintypes

    root = (os.environ.get("SystemDrive") or "C:") + "\\"
    serial = wintypes.DWORD(0)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), None, 0, ctypes.byref(serial), None, None, None, 0
    )
    if not ok:
        raise OSError("GetVolumeInformationW failed")
    return f"{serial.value:08X}"


def _raw_machine_id() -> str:
    if sys.platform == "win32":
        return f"{_windows_machine_guid()}|{_windows_volume_serial()}"
    # Development fallback for non-Windows systems.
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p) as f:
                return f.read().strip() + "|dev"
        except OSError:
            continue
    import uuid

    return f"{uuid.getnode():012x}|dev"


def machine_id() -> str:
    return hashlib.sha256(("MistuGorjetas|" + _raw_machine_id()).encode()).hexdigest()


# -------------------------------------------------------------------- DPAPI
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes):
        buf = ctypes.create_string_buffer(b, len(b))
        return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    CRYPTPROTECT_LOCAL_MACHINE = 0x4
    flags = CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE

    blob_in, _buf_in = blob(data)
    blob_ent, _buf_ent = blob(_ENTROPY)
    blob_out = DATA_BLOB()
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in), ctypes.c_wchar_p("MistuGorjetas"), ctypes.byref(blob_ent),
            None, None, flags, ctypes.byref(blob_out),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, ctypes.byref(blob_ent),
            None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
    if not ok:
        raise OSError("DPAPI operation failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def _seal(data: bytes) -> bytes:
    return _dpapi(data, True) if sys.platform == "win32" else data


def _unseal(data: bytes) -> bytes:
    return _dpapi(data, False) if sys.platform == "win32" else data


# --------------------------------------------------------------- activation
class Status(Enum):
    OK = "ok"
    NOT_ACTIVATED = "not_activated"
    WRONG_MACHINE = "wrong_machine"


def check_activation() -> Status:
    path = paths.activation_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Status.NOT_ACTIVATED
    except OSError:
        log.exception("cannot read activation record")
        return Status.NOT_ACTIVATED

    if not raw.startswith(RECORD_MAGIC):
        return Status.WRONG_MACHINE
    try:
        record = json.loads(_unseal(raw[len(RECORD_MAGIC):]).decode("utf-8"))
    except Exception:
        # Typically: the file was copied from another PC and DPAPI refuses it.
        log.warning("activation record could not be decrypted")
        return Status.WRONG_MACHINE

    try:
        current = machine_id()
    except Exception:
        log.exception("cannot compute machine ID")
        return Status.WRONG_MACHINE

    if not hmac.compare_digest(str(record.get("machine", "")), current):
        return Status.WRONG_MACHINE
    if record.get("key") != key_fingerprint():
        return Status.NOT_ACTIVATED
    return Status.OK


def activate(key: str) -> bool:
    """Verify the key and bind this installation to the current machine."""
    if not verify_key(key):
        return False
    record = {
        "v": 1,
        "machine": machine_id(),
        "key": key_fingerprint(),
        "activated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = paths.activation_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(RECORD_MAGIC + _seal(json.dumps(record).encode("utf-8")))
    os.replace(tmp, path)
    return True
