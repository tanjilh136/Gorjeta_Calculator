"""File-system locations used by the application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_ID

DB_FILENAME = "gorjetas.db"
ACTIVATION_FILENAME = "activation.dat"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Folder containing bundled read-only resources (fonts, icon)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def user_data_dir() -> Path:
    """Per-user data folder: %APPDATA%\\MistuGorjetas (never Program Files).

    The MISTU_DATA_DIR environment variable overrides it (development/testing).
    """
    override = os.environ.get("MISTU_DATA_DIR")
    if override:
        base = Path(override)
    elif is_windows():
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def machine_data_dir() -> Path:
    """Machine-wide folder for the activation record: %PROGRAMDATA%\\MistuGorjetas."""
    override = os.environ.get("MISTU_PROGRAMDATA_DIR")
    if override:
        base = Path(override)
    elif is_windows():
        base = Path(os.environ.get("PROGRAMDATA") or r"C:\ProgramData") / APP_ID
    else:
        base = user_data_dir() / "programdata"
    return base


def db_path() -> Path:
    return user_data_dir() / DB_FILENAME


def activation_path() -> Path:
    return machine_data_dir() / ACTIVATION_FILENAME


def log_path() -> Path:
    return user_data_dir() / "mistu_gorjetas.log"


def default_backup_dir() -> str:
    """Google Drive for Desktop folder if one can be found, else G:\\My Drive."""
    folder_name = "MistuGorjetas Backups"
    if is_windows():
        # Google Drive for Desktop mounts a virtual drive (G: by default) whose
        # root contains "My Drive" (or a localised name).
        drive_names = ("My Drive", "O meu disco", "Meu Drive", "A minha unidade")
        letters = "GHIJKLMNOPQRSTUVWXYZDEF"
        for letter in letters:
            for name in drive_names:
                candidate = Path(f"{letter}:\\") / name
                try:
                    if candidate.is_dir():
                        return str(candidate / folder_name)
                except OSError:
                    continue
        return str(Path("G:\\") / "My Drive" / folder_name)
    return str(Path.home() / "Google Drive" / "My Drive" / folder_name)
