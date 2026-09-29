"""Backups: one file per year (gorjetas_2026.db ...) in the chosen folder."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import paths
from .db import Database, is_valid_database, readonly_uri

log = logging.getLogger(__name__)

# Settings that belong to this computer and are kept when restoring a backup.
LOCAL_SETTINGS = ("language", "backup_path")


class BackupError(Exception):
    pass


def backup_folder(db: Database) -> str:
    return db.get_setting("backup_path") or paths.default_backup_dir()


def backup_file_name(year: int) -> str:
    return f"gorjetas_{year}.db"


def _copy_database(src: sqlite3.Connection, dest_path: Path) -> None:
    dest = sqlite3.connect(str(dest_path))
    try:
        src.backup(dest)
    finally:
        dest.close()


def make_backup(db: Database, folder: str | None = None, today: date | None = None) -> Path:
    """Copy the live database to <folder>/gorjetas_<year>.db (overwriting that year's file)."""
    folder_path = Path(folder or backup_folder(db))
    year = (today or date.today()).year
    try:
        # Only the last folder level is created: if its parent is missing (e.g. the
        # Google Drive disk is not mounted) the folder counts as unreachable.
        folder_path.mkdir(exist_ok=True)
        target = folder_path / backup_file_name(year)
        tmp = folder_path / (backup_file_name(year) + ".tmp")
        if tmp.exists():
            tmp.unlink()
        _copy_database(db.conn, tmp)
        os.replace(tmp, target)
    except (OSError, sqlite3.Error) as exc:
        log.warning("backup to %s failed: %s", folder_path, exc)
        raise BackupError(str(exc)) from exc
    log.info("backup written to %s", target)
    return target


def restore_backup(db: Database, source: Path) -> Path:
    """Replace the live data with a backup file. Returns the safety copy of the
    previous data, written next to the live database."""
    if not is_valid_database(source):
        raise BackupError("not a Mistu Gorjetas backup")
    if source.resolve() == db.path.resolve():
        raise BackupError("cannot restore the live database onto itself")

    keep = {k: db.get_setting(k) for k in LOCAL_SETTINGS}

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety = db.path.with_name(f"before_restore_{stamp}.db")
    try:
        _copy_database(db.conn, safety)
        src = sqlite3.connect(readonly_uri(source), uri=True)
        try:
            src.backup(db.conn)
        finally:
            src.close()
    except (OSError, sqlite3.Error) as exc:
        raise BackupError(str(exc)) from exc

    db.reopen()
    for k, v in keep.items():
        if v is not None:
            db.set_setting(k, v)
    return safety

