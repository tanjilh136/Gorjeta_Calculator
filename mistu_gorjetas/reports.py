"""Builds the data for the weekly and final exports (independent of the PDF layout)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from .db import Database, Day, Staff, monday_of
from .money import deduction_cents, split_equally
from .schedule import FERIAS, Schedule

# Cell states for the weekly table
VALUE, ABSENT, NO_DATA = "value", "absent", "nodata"
# Note kinds for the Notes column
NOTE_FERIAS, NOTE_DAY = FERIAS, "day"


@dataclass
class Note:
    """One entry of a person's Notes cell in an export."""

    kind: str  # NOTE_FERIAS: holiday start..end overlapping the period; NOTE_DAY: typed note
    start: date
    end: date | None = None
    text: str = ""


def period_notes(sched: Schedule, saved: dict[date, Day], staff_id: int) -> list[Note]:
    """Holidays overlapping the period first, then the notes typed on the Daily Sheet."""
    notes = [Note(NOTE_FERIAS, f.start, f.end) for f in sched.ferias_of(staff_id)]
    for d in sorted(saved):
        text = saved[d].notes.get(staff_id)
        if text:
            notes.append(Note(NOTE_DAY, d, None, text))
    return notes


@dataclass
class DayShares:
    has_data: bool
    present_ids: set[int] = field(default_factory=set)
    cash_share: int = 0
    card_share: int = 0


def day_shares(day: Day | None) -> DayShares:
    if day is None:
        return DayShares(False)
    present = day.present_ids
    n = len(present)
    return DayShares(
        True,
        present,
        split_equally(day.cash_total_cents, n),
        split_equally(day.card_total_cents, n),
    )


def staff_for_period(db: Database, start: date, end: date) -> list[Staff]:
    """Staff shown in an export: active staff who existed during the period, plus
    anyone (active or archived) present on at least one day of the period.
    Returned in staff list order."""
    with_presence = db.staff_with_presence(start, end)
    result = []
    for s in db.list_staff():
        if s.id in with_presence:
            result.append(s)
        elif s.is_active and s.created_at[:10] <= end.isoformat():
            result.append(s)
    return result


# ------------------------------------------------------------------ weekly
@dataclass
class WeeklyCell:
    state: str
    cash: int = 0
    card: int = 0
    reason: str | None = None  # for ABSENT cells: FOLGA / FERIAS when planned


@dataclass
class WeeklyRow:
    staff: Staff
    cells: list[WeeklyCell]
    total_cash: int
    total_card: int
    notes: list[Note] = field(default_factory=list)


@dataclass
class WeeklyReport:
    monday: date
    days: list[date]
    has_data: list[bool]
    rows: list[WeeklyRow]
    day_totals: list[tuple[int, int]]  # per day (cash, card), sum of shares
    total_cash: int
    total_card: int

    @property
    def sunday(self) -> date:
        return self.days[-1]


def build_weekly(db: Database, any_day: date) -> WeeklyReport:
    monday = monday_of(any_day)
    days = [monday + timedelta(days=i) for i in range(7)]
    saved = db.get_days(days[0], days[-1])
    shares = [day_shares(saved.get(d)) for d in days]
    sched = Schedule(db, days[0], days[-1])

    rows: list[WeeklyRow] = []
    day_totals = [[0, 0] for _ in days]
    for s in staff_for_period(db, days[0], days[-1]):
        cells = []
        tc = tk = 0
        for i, sh in enumerate(shares):
            if not sh.has_data:
                cells.append(WeeklyCell(NO_DATA))
            elif s.id in sh.present_ids:
                cells.append(WeeklyCell(VALUE, sh.cash_share, sh.card_share))
                tc += sh.cash_share
                tk += sh.card_share
                day_totals[i][0] += sh.cash_share
                day_totals[i][1] += sh.card_share
            else:
                cells.append(WeeklyCell(ABSENT, reason=sched.reason(s.id, days[i])))
        rows.append(WeeklyRow(s, cells, tc, tk, period_notes(sched, saved, s.id)))

    return WeeklyReport(
        monday=monday,
        days=days,
        has_data=[sh.has_data for sh in shares],
        rows=rows,
        day_totals=[(c, k) for c, k in day_totals],
        total_cash=sum(r.total_cash for r in rows),
        total_card=sum(r.total_card for r in rows),
    )


# ------------------------------------------------------------------- final
@dataclass
class FinalRow:
    staff: Staff
    weeks: list[tuple[int, int]]  # (cash, card) per week
    total_cash: int
    total_card: int
    total: int
    deduction: int
    receivable: int
    notes: list[Note] = field(default_factory=list)


@dataclass
class FinalReport:
    start: date
    end: date
    weeks: list[tuple[date, date]]
    week_has_data: list[bool]
    deduction_pct: Decimal
    rows: list[FinalRow]
    week_totals: list[tuple[int, int]]
    total_cash: int
    total_card: int
    total: int
    deduction: int
    receivable: int


def build_final(db: Database, start: date, end: date, deduction_pct: Decimal) -> FinalReport:
    if start.weekday() != 0 or end.weekday() != 6 or end < start:
        raise ValueError("range must run from a Monday to a Sunday")

    weeks: list[tuple[date, date]] = []
    m = start
    while m <= end:
        weeks.append((m, m + timedelta(days=6)))
        m += timedelta(days=7)

    saved = db.get_days(start, end)
    shares = {d: day_shares(day) for d, day in saved.items()}
    sched = Schedule(db, start, end)
    week_has_data = [
        any(ws <= d <= we for d in saved) for ws, we in weeks
    ]

    rows: list[FinalRow] = []
    for s in staff_for_period(db, start, end):
        per_week = []
        for ws, we in weeks:
            cash = card = 0
            for d, sh in shares.items():
                if ws <= d <= we and s.id in sh.present_ids:
                    cash += sh.cash_share
                    card += sh.card_share
            per_week.append((cash, card))
        total_cash = sum(c for c, _ in per_week)
        total_card = sum(k for _, k in per_week)
        total = total_cash + total_card
        # Tax deduction applies to card tips only; cash is paid out in full:
        # receivable = cash + (card - card x pct).
        ded = deduction_cents(total_card, deduction_pct)
        rows.append(FinalRow(
            s, per_week, total_cash, total_card, total, ded, total - ded,
            period_notes(sched, saved, s.id),
        ))

    week_totals = [
        (sum(r.weeks[i][0] for r in rows), sum(r.weeks[i][1] for r in rows))
        for i in range(len(weeks))
    ]
    return FinalReport(
        start=start,
        end=end,
        weeks=weeks,
        week_has_data=week_has_data,
        deduction_pct=deduction_pct,
        rows=rows,
        week_totals=week_totals,
        total_cash=sum(r.total_cash for r in rows),
        total_card=sum(r.total_card for r in rows),
        total=sum(r.total for r in rows),
        deduction=sum(r.deduction for r in rows),
        receivable=sum(r.receivable for r in rows),
    )
