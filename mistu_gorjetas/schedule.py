"""Planned absences: weekly days off (folgas) and holidays (ferias).

They only decide who starts unticked on a NEW daily sheet, and label absences in
the Daily Sheet notes and in the exports. Saved days are never changed.
"""

from __future__ import annotations

from datetime import date

from .db import Database, Ferias

FOLGA = "folga"
FERIAS = "ferias"


class Schedule:
    """Folgas and the ferias overlapping a period, loaded once for fast lookups."""

    def __init__(self, db: Database, start: date, end: date):
        self.folgas = db.get_folgas()
        self.ferias = db.ferias_between(start, end)

    def reason(self, staff_id: int, d: date) -> str | None:
        """FERIAS, FOLGA or None. Ferias win when both apply."""
        for f in self.ferias:
            if f.staff_id == staff_id and f.covers(d):
                return FERIAS
        if d.weekday() in self.folgas.get(staff_id, ()):
            return FOLGA
        return None

    def ferias_of(self, staff_id: int) -> list[Ferias]:
        return [f for f in self.ferias if f.staff_id == staff_id]


def reasons_for_day(db: Database, d: date, staff_ids) -> dict[int, str]:
    """staff_id -> FERIAS / FOLGA for everyone with a planned absence on d."""
    sched = Schedule(db, d, d)
    result = {}
    for sid in staff_ids:
        r = sched.reason(sid, d)
        if r:
            result[sid] = r
    return result
