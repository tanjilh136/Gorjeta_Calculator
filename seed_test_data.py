"""Fill a database with test data: 25 staff and 5 full weeks of days.

Usage:
    python seed_test_data.py                 # seeds the app's own database
    python seed_test_data.py --db test.db    # seeds another file
    python seed_test_data.py --weeks 8 --yes

The last 5 complete weeks (Monday-Sunday, ending last Sunday) are filled.
Special cases included for checking the exports:
  * one closed day with no data saved at all (shows "—")
  * weekly days off (folgas) for everyone, some with two (shows "FO")
  * holidays (ferias): one inside week 3, one running past the last week,
    one planned for next month (shows "FÉ" and dates in the Notes column)
  * a few random extra absences (shows "✗") and typed notes
  * one staff member archived after week 2 (still in exports for weeks 1-2)
  * one staff member added in week 4 (not in earlier weeks)
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta

from mistu_gorjetas import paths
from mistu_gorjetas.db import Database, monday_of
from mistu_gorjetas.schedule import Schedule

NAMES = [
    ("Ana Silva", "sala"), ("João Ferreira", "sala"), ("Maria Santos", "sala"),
    ("Pedro Costa", "sala"), ("Inês Rodrigues", "sala"), ("Tiago Martins", "sala"),
    ("Beatriz Sousa", "sala"), ("Rui Oliveira", "sala"), ("Carla Pereira", "sala"),
    ("Miguel Carvalho", "cozinha"), ("Sofia Gomes", "cozinha"), ("Bruno Lopes", "cozinha"),
    ("Catarina Marques", "cozinha"), ("Diogo Almeida", "cozinha"), ("Helena Ribeiro", "cozinha"),
    ("Nuno Fernandes", "cozinha"), ("Rita Pinto", "copa"), ("André Teixeira", "copa"),
    ("Joana Moreira", "copa"), ("Filipe Correia", "copa"), ("Marta Mendes", "copa"),
    ("Ricardo Nunes", "other"), ("Luísa Soares", "other"), ("Gonçalo Vieira", "sala"),
    ("Mariana Monteiro-Albuquerque", "sala"),
]

NOTES = ["Saiu mais cedo", "Chegou atrasado", "Troca de turno com colega", "Fez horas extra"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="database file (default: the app database)")
    ap.add_argument("--weeks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--yes", action="store_true", help="do not ask before wiping existing data")
    args = ap.parse_args()

    db_file = args.db or str(paths.db_path())
    db = Database(db_file)
    existing = db.conn.execute("SELECT (SELECT COUNT(*) FROM staff) + (SELECT COUNT(*) FROM days)").fetchone()[0]
    if existing and not args.yes:
        answer = input(f"{db_file} already contains data. Wipe it and seed test data? [y/N] ")
        if answer.strip().lower() not in ("y", "yes", "s", "sim"):
            print("Cancelled.")
            return 1

    rng = random.Random(args.seed)
    last_sunday = monday_of(date.today()) - timedelta(days=1)
    first_monday = last_sunday - timedelta(days=7 * args.weeks - 1)
    all_days = [first_monday + timedelta(days=i) for i in range(7 * args.weeks)]

    with db.conn:
        db.conn.execute("DELETE FROM ferias")
        db.conn.execute("DELETE FROM folgas")
        db.conn.execute("DELETE FROM attendance")
        db.conn.execute("DELETE FROM days")
        db.conn.execute("DELETE FROM staff")
        db.conn.execute("DELETE FROM sqlite_sequence WHERE name = 'staff'")

    created_before = datetime.combine(first_monday - timedelta(days=30), datetime.min.time())
    ids: list[int] = []
    for name, section in NAMES[:24]:
        ids.append(db.add_staff(name, section, created_at=created_before.isoformat(timespec="seconds")))
    archived_id = ids[4]  # Inês Rodrigues leaves after week 2
    late_joiner_date = first_monday + timedelta(days=21) if args.weeks >= 4 else first_monday
    late_id = db.add_staff(*NAMES[24], created_at=datetime.combine(
        late_joiner_date, datetime.min.time()).isoformat(timespec="seconds"))
    ids.append(late_id)

    # Folgas: one weekday each, every third person a second one.
    for i, sid in enumerate(ids):
        db.set_folga(sid, i % 7, True)
        if i % 3 == 0:
            db.set_folga(sid, (i + 3) % 7, True)
    # Ferias
    db.add_ferias(ids[1], first_monday + timedelta(days=14), first_monday + timedelta(days=20))
    db.add_ferias(ids[10], last_sunday - timedelta(days=4), last_sunday + timedelta(days=10))
    db.add_ferias(ids[2], last_sunday + timedelta(days=22), last_sunday + timedelta(days=35))
    sched = Schedule(db, first_monday, last_sunday)

    closed_day = first_monday + timedelta(days=7)  # Monday of week 2: restaurant closed
    for d in all_days:
        if d == closed_day:
            continue
        week_no = (d - first_monday).days // 7
        roster = [
            sid for sid in ids
            if not (sid == archived_id and week_no >= 2) and not (sid == late_id and d < late_joiner_date)
        ]
        attendance = {sid: sched.reason(sid, d) is None and rng.random() > 0.08 for sid in roster}
        if not any(attendance.values()):
            attendance[roster[0]] = True
        notes = {sid: rng.choice(NOTES) for sid in roster if rng.random() < 0.02}
        weekend = d.weekday() >= 4
        cash = rng.randint(80_00, 260_00) + (rng.randint(50_00, 150_00) if weekend else 0) + rng.randint(0, 99)
        card = rng.randint(120_00, 420_00) + (rng.randint(80_00, 250_00) if weekend else 0) + rng.randint(0, 99)
        db.save_day(d, cash, card, attendance, notes)

    db.set_staff_active(archived_id, False)
    db.set_setting("deduction_pct", "10")
    db.close()
    print(f"Seeded {len(ids)} staff and {len(all_days) - 1} days "
          f"({first_monday:%d/%m/%Y} to {last_sunday:%d/%m/%Y}) into {db_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
