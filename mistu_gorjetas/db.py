"""SQLite storage. One file in %APPDATA%\\MistuGorjetas."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import pathname2url

SCHEMA_VERSION = 2

SECTIONS = ("sala", "cozinha", "copa", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    section     TEXT    NOT NULL DEFAULT 'sala',
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS days (
    date              TEXT    PRIMARY KEY,          -- YYYY-MM-DD
    cash_total_cents  INTEGER NOT NULL DEFAULT 0 CHECK (cash_total_cents >= 0),
    card_total_cents  INTEGER NOT NULL DEFAULT 0 CHECK (card_total_cents >= 0),
    updated_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    date      TEXT    NOT NULL REFERENCES days(date) ON DELETE CASCADE,
    staff_id  INTEGER NOT NULL REFERENCES staff(id),
    present   INTEGER NOT NULL DEFAULT 0,
    note      TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (date, staff_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_staff ON attendance(staff_id);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- Weekly days off (folgas): 0 = Monday ... 6 = Sunday.
CREATE TABLE IF NOT EXISTS folgas (
    staff_id  INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    weekday   INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    PRIMARY KEY (staff_id, weekday)
);

-- Scheduled holidays (ferias), both dates inclusive.
CREATE TABLE IF NOT EXISTS ferias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id    INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_ferias_dates ON ferias(start_date, end_date);
"""

REQUIRED_TABLES = {"staff", "days", "attendance", "settings"}

DEFAULT_SETTINGS = {
    "language": "pt",
    "deduction_pct": "0",
}


@dataclass
class Staff:
    id: int
    name: str
    section: str
    is_active: bool
    sort_order: int
    created_at: str


@dataclass
class Day:
    date: date
    cash_total_cents: int
    card_total_cents: int
    updated_at: str
    attendance: dict[int, bool]  # staff_id -> present
    notes: dict[int, str] = field(default_factory=dict)  # staff_id -> note (non-empty only)

    @property
    def present_ids(self) -> set[int]:
        return {sid for sid, p in self.attendance.items() if p}


@dataclass
class Ferias:
    id: int
    staff_id: int
    start: date
    end: date

    def covers(self, d: date) -> bool:
        return self.start <= d <= self.end

    def overlaps(self, start: date, end: date) -> bool:
        return self.start <= end and start <= self.end


def iso(d: date) -> str:
    return d.isoformat()


def now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def readonly_uri(path: Path | str) -> str:
    return "file:" + pathname2url(str(Path(path).resolve())) + "?mode=ro"


def is_valid_database(path: Path | str) -> bool:
    """True if the file is a SQLite database with this application's tables."""
    try:
        conn = sqlite3.connect(readonly_uri(path), uri=True)
        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return REQUIRED_TABLES <= {r[0] for r in rows}


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.conn = connect(self.path)
        self._init_schema()

    # ------------------------------------------------------------------ setup
    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)
            self._migrate()
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            for key, value in DEFAULT_SETTINGS.items():
                self.conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
                )

    def _migrate(self) -> None:
        """Bring databases (and restored backups) from older versions up to date."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(attendance)")}
        if "note" not in cols:  # version 1 -> 2: notes per person per day
            self.conn.execute("ALTER TABLE attendance ADD COLUMN note TEXT NOT NULL DEFAULT ''")

    def close(self) -> None:
        self.conn.close()

    def reopen(self) -> None:
        self.conn.close()
        self.conn = connect(self.path)
        self._init_schema()

    # --------------------------------------------------------------- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None or row["value"] is None:
            return default
        return row["value"]

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ------------------------------------------------------------------ staff
    @staticmethod
    def _staff(row: sqlite3.Row) -> Staff:
        return Staff(
            id=row["id"],
            name=row["name"],
            section=row["section"],
            is_active=bool(row["is_active"]),
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    def list_staff(self, active_only: bool = False) -> list[Staff]:
        sql = "SELECT * FROM staff"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY sort_order, id"
        return [self._staff(r) for r in self.conn.execute(sql)]

    def get_staff(self, staff_id: int) -> Staff | None:
        row = self.conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
        return self._staff(row) if row else None

    def add_staff(self, name: str, section: str, created_at: str | None = None) -> int:
        with self.conn:
            (max_order,) = self.conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM staff"
            ).fetchone()
            cur = self.conn.execute(
                "INSERT INTO staff(name, section, is_active, sort_order, created_at) "
                "VALUES (?, ?, 1, ?, ?)",
                (name.strip(), section, max_order + 1, created_at or now_str()),
            )
            return int(cur.lastrowid)

    def update_staff(self, staff_id: int, name: str, section: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE staff SET name = ?, section = ? WHERE id = ?",
                (name.strip(), section, staff_id),
            )

    def set_staff_active(self, staff_id: int, active: bool) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE staff SET is_active = ? WHERE id = ?", (1 if active else 0, staff_id)
            )

    def staff_has_history(self, staff_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM attendance WHERE staff_id = ? LIMIT 1", (staff_id,)
        ).fetchone()
        return row is not None

    def delete_staff(self, staff_id: int) -> None:
        """Hard delete - only allowed for staff without any history."""
        if self.staff_has_history(staff_id):
            raise ValueError("staff member has history")
        with self.conn:
            self.conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))

    def reorder_staff(self, ordered_ids: list[int]) -> None:
        with self.conn:
            for pos, sid in enumerate(ordered_ids, start=1):
                self.conn.execute("UPDATE staff SET sort_order = ? WHERE id = ?", (pos, sid))

    # ------------------------------------------------------------------- days
    def get_day(self, d: date) -> Day | None:
        row = self.conn.execute("SELECT * FROM days WHERE date = ?", (iso(d),)).fetchone()
        if row is None:
            return None
        att: dict[int, bool] = {}
        notes: dict[int, str] = {}
        for r in self.conn.execute(
            "SELECT staff_id, present, note FROM attendance WHERE date = ?", (iso(d),)
        ):
            att[r["staff_id"]] = bool(r["present"])
            if r["note"]:
                notes[r["staff_id"]] = r["note"]
        return Day(
            date=d,
            cash_total_cents=row["cash_total_cents"],
            card_total_cents=row["card_total_cents"],
            updated_at=row["updated_at"],
            attendance=att,
            notes=notes,
        )

    def get_days(self, start: date, end: date) -> dict[date, Day]:
        """All saved days in [start, end], with attendance."""
        days: dict[date, Day] = {}
        for row in self.conn.execute(
            "SELECT * FROM days WHERE date BETWEEN ? AND ? ORDER BY date",
            (iso(start), iso(end)),
        ):
            d = date.fromisoformat(row["date"])
            days[d] = Day(d, row["cash_total_cents"], row["card_total_cents"], row["updated_at"], {})
        for row in self.conn.execute(
            "SELECT date, staff_id, present, note FROM attendance WHERE date BETWEEN ? AND ?",
            (iso(start), iso(end)),
        ):
            d = date.fromisoformat(row["date"])
            if d in days:
                days[d].attendance[row["staff_id"]] = bool(row["present"])
                if row["note"]:
                    days[d].notes[row["staff_id"]] = row["note"]
        return days

    def save_day(
        self,
        d: date,
        cash_cents: int,
        card_cents: int,
        attendance: dict[int, bool],
        notes: dict[int, str] | None = None,
    ) -> None:
        """Create or overwrite a day with its attendance and notes, atomically."""
        notes = notes or {}
        if cash_cents < 0 or card_cents < 0:
            raise ValueError("negative amount")
        if (cash_cents > 0 or card_cents > 0) and not any(attendance.values()):
            raise ValueError("nobody present")
        with self.conn:
            self.conn.execute(
                "INSERT INTO days(date, cash_total_cents, card_total_cents, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(date) DO UPDATE SET "
                "cash_total_cents = excluded.cash_total_cents, "
                "card_total_cents = excluded.card_total_cents, "
                "updated_at = excluded.updated_at",
                (iso(d), cash_cents, card_cents, now_str()),
            )
            self.conn.execute("DELETE FROM attendance WHERE date = ?", (iso(d),))
            self.conn.executemany(
                "INSERT INTO attendance(date, staff_id, present, note) VALUES (?, ?, ?, ?)",
                [
                    (iso(d), sid, 1 if p else 0, (notes.get(sid) or "").strip())
                    for sid, p in attendance.items()
                ],
            )

    def day_summaries(self, year: int | None = None) -> list[sqlite3.Row]:
        """date, cash, card, present_count for every saved day, newest first."""
        sql = (
            "SELECT d.date, d.cash_total_cents, d.card_total_cents, "
            "COALESCE(SUM(a.present), 0) AS present_count "
            "FROM days d LEFT JOIN attendance a ON a.date = d.date "
        )
        params: tuple = ()
        if year is not None:
            sql += "WHERE d.date BETWEEN ? AND ? "
            params = (f"{year:04d}-01-01", f"{year:04d}-12-31")
        sql += "GROUP BY d.date ORDER BY d.date DESC"
        return list(self.conn.execute(sql, params))

    def years_with_data(self) -> list[int]:
        rows = self.conn.execute(
            "SELECT DISTINCT substr(date, 1, 4) AS y FROM days ORDER BY y DESC"
        )
        return [int(r["y"]) for r in rows]

    def count_days(self, start: date, end: date) -> int:
        (n,) = self.conn.execute(
            "SELECT COUNT(*) FROM days WHERE date BETWEEN ? AND ?", (iso(start), iso(end))
        ).fetchone()
        return int(n)

    def delete_days(self, start: date, end: date) -> int:
        """Delete saved days (and their attendance) in [start, end]."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM attendance WHERE date BETWEEN ? AND ?", (iso(start), iso(end))
            )
            cur = self.conn.execute(
                "DELETE FROM days WHERE date BETWEEN ? AND ?", (iso(start), iso(end))
            )
            return cur.rowcount

    def purge_older_than(self, cutoff: date) -> int:
        """Delete day records (and holidays that ended) strictly before cutoff."""
        with self.conn:
            self.conn.execute("DELETE FROM ferias WHERE end_date < ?", (iso(cutoff),))
            self.conn.execute("DELETE FROM attendance WHERE date < ?", (iso(cutoff),))
            cur = self.conn.execute("DELETE FROM days WHERE date < ?", (iso(cutoff),))
            return cur.rowcount

    def staff_with_presence(self, start: date, end: date) -> set[int]:
        rows = self.conn.execute(
            "SELECT DISTINCT staff_id FROM attendance WHERE present = 1 AND date BETWEEN ? AND ?",
            (iso(start), iso(end)),
        )
        return {r["staff_id"] for r in rows}

    # ----------------------------------------------------- folgas (days off)
    def get_folgas(self) -> dict[int, set[int]]:
        """staff_id -> weekdays off (0 = Monday ... 6 = Sunday)."""
        result: dict[int, set[int]] = {}
        for r in self.conn.execute("SELECT staff_id, weekday FROM folgas"):
            result.setdefault(r["staff_id"], set()).add(r["weekday"])
        return result

    def set_folga(self, staff_id: int, weekday: int, off: bool) -> None:
        with self.conn:
            if off:
                self.conn.execute(
                    "INSERT OR IGNORE INTO folgas(staff_id, weekday) VALUES (?, ?)", (staff_id, weekday)
                )
            else:
                self.conn.execute(
                    "DELETE FROM folgas WHERE staff_id = ? AND weekday = ?", (staff_id, weekday)
                )

    # ---------------------------------------------------- ferias (holidays)
    @staticmethod
    def _ferias(row: sqlite3.Row) -> Ferias:
        return Ferias(
            row["id"], row["staff_id"],
            date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"]),
        )

    def list_ferias(self) -> list[Ferias]:
        rows = self.conn.execute("SELECT * FROM ferias ORDER BY start_date DESC, id DESC")
        return [self._ferias(r) for r in rows]

    def ferias_between(self, start: date, end: date) -> list[Ferias]:
        """Holidays that overlap [start, end], oldest first."""
        rows = self.conn.execute(
            "SELECT * FROM ferias WHERE start_date <= ? AND end_date >= ? ORDER BY start_date, id",
            (iso(end), iso(start)),
        )
        return [self._ferias(r) for r in rows]

    def ferias_conflict(self, staff_id: int, start: date, end: date, exclude_id: int | None = None) -> Ferias | None:
        """Another holiday of the same person overlapping [start, end], if any."""
        for f in self.ferias_between(start, end):
            if f.staff_id == staff_id and f.id != exclude_id:
                return f
        return None

    def add_ferias(self, staff_id: int, start: date, end: date) -> int:
        if end < start:
            raise ValueError("end before start")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO ferias(staff_id, start_date, end_date) VALUES (?, ?, ?)",
                (staff_id, iso(start), iso(end)),
            )
            return int(cur.lastrowid)

    def update_ferias(self, ferias_id: int, staff_id: int, start: date, end: date) -> None:
        if end < start:
            raise ValueError("end before start")
        with self.conn:
            self.conn.execute(
                "UPDATE ferias SET staff_id = ?, start_date = ?, end_date = ? WHERE id = ?",
                (staff_id, iso(start), iso(end), ferias_id),
            )

    def delete_ferias(self, ferias_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM ferias WHERE id = ?", (ferias_id,))


def retention_cutoff(today: date, years: int = 5) -> date:
    """Same calendar day `years` years ago (29 Feb -> 28 Feb)."""
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def sunday_of(d: date) -> date:
    return monday_of(d) + timedelta(days=6)
