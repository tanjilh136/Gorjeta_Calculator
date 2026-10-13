"""Unit tests for money, calculations, reports, backup and licensing.

Run with:  python -m unittest discover -s tests
"""

from __future__ import annotations

import atexit
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="mistu_test_")
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)
os.environ["MISTU_DATA_DIR"] = _TMP
os.environ["MISTU_PROGRAMDATA_DIR"] = os.path.join(_TMP, "programdata")

from mistu_gorjetas import backup, build_config, licensing  # noqa: E402
from mistu_gorjetas.db import Database, retention_cutoff  # noqa: E402
from mistu_gorjetas.money import (  # noqa: E402
    MoneyError,
    deduction_cents,
    format_euro,
    format_percent,
    parse_amount,
    parse_percent,
    split_equally,
)
from mistu_gorjetas.reports import (  # noqa: E402
    ABSENT,
    NO_DATA,
    NOTE_DAY,
    NOTE_FERIAS,
    VALUE,
    build_final,
    build_weekly,
)
from mistu_gorjetas.schedule import FERIAS, FOLGA, reasons_for_day  # noqa: E402

MON = date(2026, 8, 31)  # a Monday


class MoneyTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_euro(123456), "€1.234,56")
        self.assertEqual(format_euro(5), "€0,05")
        self.assertEqual(format_euro(100000000), "€1.000.000,00")
        self.assertEqual(format_euro(-150), "-€1,50")

    def test_parse(self):
        cases = {
            "1.234,56": 123456, "1234,56": 123456, "1234.56": 123456, "1 234,5": 123450,
            "€12": 1200, "": 0, "1.234": 123400, "12.5": 1250, ",5": 50, "1,234.56": 123456,
            "1.234.567,89": 123456789,
        }
        for text, cents in cases.items():
            self.assertEqual(parse_amount(text), cents, text)
        for bad in ("abc", "1,2,3", "12,345", "1.23.4", "-5", "1,234,5"):
            with self.assertRaises(MoneyError, msg=bad):
                parse_amount(bad)

    def test_split_rounds_down(self):
        self.assertEqual(split_equally(10000, 3), 3333)
        self.assertEqual(split_equally(5, 3), 1)
        self.assertEqual(split_equally(100, 0), 0)

    def test_deduction_half_up(self):
        self.assertEqual(deduction_cents(1000, Decimal("11.5")), 115)
        self.assertEqual(deduction_cents(10, Decimal("15")), 2)  # 1.5 -> 2
        self.assertEqual(deduction_cents(10, Decimal("25")), 3)  # 2.5 -> 3
        self.assertEqual(deduction_cents(78049, Decimal("11.5")), 8976)  # 8975.635
        self.assertEqual(format_percent(parse_percent("11.50")), "11,5")
        self.assertEqual(format_percent(parse_percent("12")), "12")


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(dir=_TMP)
        self.db = Database(Path(self.dir) / "t.db")
        created = "2026-01-01T00:00:00"
        self.a = self.db.add_staff("Ana", "sala", created)
        self.b = self.db.add_staff("Bruno", "cozinha", created)
        self.c = self.db.add_staff("Carla", "copa", created)

    def tearDown(self):
        self.db.close()


class DayTests(DbTestCase):
    def test_save_overwrites(self):
        self.db.save_day(MON, 1000, 2000, {self.a: True, self.b: False})
        self.db.save_day(MON, 3000, 0, {self.a: True, self.b: True, self.c: False})
        day = self.db.get_day(MON)
        self.assertEqual((day.cash_total_cents, day.card_total_cents), (3000, 0))
        self.assertEqual(day.present_ids, {self.a, self.b})

    def test_nobody_present_blocked(self):
        with self.assertRaises(ValueError):
            self.db.save_day(MON, 100, 0, {self.a: False})
        self.db.save_day(MON, 0, 0, {self.a: False})  # zero amounts: allowed

    def test_no_hard_delete_with_history(self):
        self.db.save_day(MON, 100, 0, {self.a: True})
        with self.assertRaises(ValueError):
            self.db.delete_staff(self.a)
        self.db.delete_staff(self.c)
        self.assertIsNone(self.db.get_staff(self.c))

    def test_reorder(self):
        self.db.reorder_staff([self.c, self.a, self.b])
        self.assertEqual([s.id for s in self.db.list_staff()], [self.c, self.a, self.b])

    def test_retention(self):
        old = date(2021, 9, 28)
        self.db.save_day(old, 100, 0, {self.a: True})
        self.db.save_day(MON, 100, 0, {self.a: True})
        removed = self.db.purge_older_than(retention_cutoff(date(2026, 9, 29)))
        self.assertEqual(removed, 1)
        self.assertIsNone(self.db.get_day(old))
        self.assertEqual(retention_cutoff(date(2028, 2, 29)), date(2023, 2, 28))


class ReportTests(DbTestCase):
    def test_weekly(self):
        self.db.save_day(MON, 1000, 101, {self.a: True, self.b: True, self.c: False})
        self.db.save_day(MON + timedelta(days=1), 999, 0, {self.a: True, self.b: True, self.c: True})
        self.db.set_staff_active(self.c, False)
        r = build_weekly(self.db, MON + timedelta(days=4))
        self.assertEqual(r.monday, MON)
        names = [row.staff.name for row in r.rows]
        self.assertEqual(names, ["Ana", "Bruno", "Carla"])  # archived Carla has records
        ana, _, carla = r.rows
        self.assertEqual((ana.cells[0].state, ana.cells[0].cash, ana.cells[0].card), (VALUE, 500, 50))
        self.assertEqual(carla.cells[0].state, ABSENT)
        self.assertEqual(carla.cells[1].cash, 333)
        self.assertEqual(ana.cells[2].state, NO_DATA)
        self.assertEqual((ana.total_cash, ana.total_card), (833, 50))
        self.assertEqual(r.day_totals[0], (1000, 100))  # 1 cent of card lost to rounding

    def test_archived_without_records_hidden(self):
        self.db.save_day(MON, 1000, 0, {self.a: True, self.b: True})
        self.db.set_staff_active(self.c, False)
        r = build_weekly(self.db, MON)
        self.assertEqual([row.staff.name for row in r.rows], ["Ana", "Bruno"])

    def test_final(self):
        self.db.save_day(MON, 1000, 1000, {self.a: True, self.b: True})
        self.db.save_day(MON + timedelta(days=7), 300, 0, {self.a: True, self.b: False})
        r = build_final(self.db, MON, MON + timedelta(days=13), Decimal("11.5"))
        self.assertEqual(len(r.weeks), 2)
        ana = r.rows[0]
        self.assertEqual(ana.weeks, [(500, 500), (300, 0)])
        self.assertEqual((ana.total_cash, ana.total_card), (800, 500))
        self.assertEqual(ana.total, 1300)
        # Deduction on card only: 500 x 11.5% = 57.5 -> 58; cash 800 untouched.
        self.assertEqual(ana.deduction, 58)
        self.assertEqual(ana.receivable, 1242)
        self.assertEqual(ana.receivable, ana.total_cash + (ana.total_card - ana.deduction))
        bruno = r.rows[1]  # cash 500 + card 500 -> deduction 57.5 -> 58
        self.assertEqual((bruno.total, bruno.deduction, bruno.receivable), (1000, 58, 942))
        self.assertEqual(r.deduction, 116)
        self.assertEqual(r.receivable, r.total - r.deduction)
        self.assertEqual(r.total, 2300)
        self.assertEqual((r.total_cash, r.total_card), (1300, 1000))
        self.assertEqual(r.total_cash + r.total_card, r.total)
        with self.assertRaises(ValueError):
            build_final(self.db, MON + timedelta(days=1), MON + timedelta(days=13), Decimal(0))


class LeaveTests(DbTestCase):
    """Folgas (weekly days off), ferias (holidays) and notes."""

    def test_folgas(self):
        self.db.set_folga(self.a, 0, True)
        self.db.set_folga(self.a, 3, True)
        self.db.set_folga(self.a, 3, True)  # idempotent
        self.db.set_folga(self.b, 6, True)
        self.assertEqual(self.db.get_folgas(), {self.a: {0, 3}, self.b: {6}})
        self.db.set_folga(self.a, 0, False)
        self.assertEqual(self.db.get_folgas()[self.a], {3})

    def test_ferias_and_conflicts(self):
        fid = self.db.add_ferias(self.a, MON, MON + timedelta(days=9))
        self.assertIsNotNone(self.db.ferias_conflict(self.a, MON + timedelta(days=9), MON + timedelta(days=12)))
        self.assertIsNone(self.db.ferias_conflict(self.a, MON + timedelta(days=10), MON + timedelta(days=12)))
        self.assertIsNone(self.db.ferias_conflict(self.b, MON, MON))  # other person
        self.assertIsNone(self.db.ferias_conflict(self.a, MON, MON, exclude_id=fid))  # editing itself
        with self.assertRaises(ValueError):
            self.db.add_ferias(self.a, MON, MON - timedelta(days=1))
        self.db.delete_staff(self.c)  # no history: allowed, cascades
        self.db.add_ferias(self.b, MON, MON)
        self.db.delete_ferias(fid)
        self.assertEqual([f.staff_id for f in self.db.list_ferias()], [self.b])

    def test_reasons_ferias_win_over_folga(self):
        self.db.set_folga(self.a, MON.weekday(), True)
        self.db.set_folga(self.b, MON.weekday(), True)
        self.db.add_ferias(self.a, MON, MON + timedelta(days=2))
        reasons = reasons_for_day(self.db, MON, [self.a, self.b, self.c])
        self.assertEqual(reasons, {self.a: FERIAS, self.b: FOLGA})
        self.assertEqual(reasons_for_day(self.db, MON + timedelta(days=1), [self.a, self.b]), {self.a: FERIAS})

    def test_notes_saved_with_day(self):
        self.db.save_day(MON, 1000, 0, {self.a: True, self.b: False}, {self.a: "  Saiu cedo ", self.b: ""})
        day = self.db.get_day(MON)
        self.assertEqual(day.notes, {self.a: "Saiu cedo"})
        self.db.save_day(MON, 1000, 0, {self.a: True, self.b: False})  # overwrite without notes
        self.assertEqual(self.db.get_day(MON).notes, {})

    def test_weekly_codes_and_notes(self):
        self.db.set_folga(self.b, MON.weekday(), True)
        self.db.add_ferias(self.c, MON - timedelta(days=3), MON + timedelta(days=1))
        self.db.save_day(MON, 900, 0, {self.a: True, self.b: False, self.c: False}, {self.a: "Extra"})
        self.db.save_day(MON + timedelta(days=2), 900, 0, {self.a: True, self.b: False, self.c: True})
        r = build_weekly(self.db, MON)
        ana, bruno, carla = r.rows
        self.assertEqual((bruno.cells[0].state, bruno.cells[0].reason), (ABSENT, FOLGA))
        self.assertEqual((carla.cells[0].state, carla.cells[0].reason), (ABSENT, FERIAS))
        self.assertEqual((bruno.cells[2].state, bruno.cells[2].reason), (ABSENT, None))  # plain absence
        self.assertEqual(carla.cells[2].state, VALUE)
        self.assertEqual([(n.kind, n.start, n.end) for n in carla.notes],
                         [(NOTE_FERIAS, MON - timedelta(days=3), MON + timedelta(days=1))])
        self.assertEqual([(n.kind, n.start, n.text) for n in ana.notes], [(NOTE_DAY, MON, "Extra")])

    def test_final_notes(self):
        self.db.add_ferias(self.a, MON + timedelta(days=12), MON + timedelta(days=30))
        self.db.add_ferias(self.a, MON + timedelta(days=60), MON + timedelta(days=70))  # outside
        self.db.save_day(MON + timedelta(days=1), 500, 500, {self.a: True, self.b: True}, {self.b: "Turno"})
        r = build_final(self.db, MON, MON + timedelta(days=13), Decimal("10"))
        ana, bruno = r.rows[0], r.rows[1]
        self.assertEqual([(n.kind, n.end) for n in ana.notes], [(NOTE_FERIAS, MON + timedelta(days=30))])
        self.assertEqual([(n.kind, n.text) for n in bruno.notes], [(NOTE_DAY, "Turno")])

    def test_retention_purges_old_ferias(self):
        self.db.add_ferias(self.a, date(2020, 1, 1), date(2020, 1, 10))
        self.db.add_ferias(self.a, date(2026, 1, 1), date(2026, 1, 10))
        self.db.purge_older_than(retention_cutoff(date(2026, 9, 29)))
        self.assertEqual([f.start.year for f in self.db.list_ferias()], [2026])


class MigrationTests(unittest.TestCase):
    def test_version1_database_is_upgraded(self):
        path = Path(tempfile.mkdtemp(dir=_TMP)) / "old.db"
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE staff (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT 'sala', is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            CREATE TABLE days (date TEXT PRIMARY KEY, cash_total_cents INTEGER NOT NULL DEFAULT 0,
                card_total_cents INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
            CREATE TABLE attendance (date TEXT NOT NULL REFERENCES days(date) ON DELETE CASCADE,
                staff_id INTEGER NOT NULL REFERENCES staff(id), present INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date, staff_id));
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO staff VALUES (1, 'Ana', 'sala', 1, 1, '2026-01-01T00:00:00');
            INSERT INTO days VALUES ('2026-08-31', 1000, 0, '2026-08-31T20:00:00');
            INSERT INTO attendance VALUES ('2026-08-31', 1, 1);
            PRAGMA user_version = 1;
        """)
        conn.commit()
        conn.close()
        db = Database(path)
        try:
            day = db.get_day(MON)
            self.assertEqual((day.cash_total_cents, day.present_ids, day.notes), (1000, {1}, {}))
            db.save_day(MON, 1000, 0, {1: True}, {1: "ok"})
            self.assertEqual(db.get_day(MON).notes, {1: "ok"})
            self.assertEqual(db.conn.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(db.get_folgas(), {})
        finally:
            db.close()


class BackupTests(DbTestCase):
    def test_backup_and_restore(self):
        self.db.save_day(MON, 1000, 0, {self.a: True})
        self.db.set_setting("language", "en")
        folder = Path(self.dir) / "backups"
        target = backup.make_backup(self.db, str(folder), today=date(2026, 5, 1))
        self.assertEqual(target.name, "gorjetas_2026.db")

        self.db.delete_days(MON, MON)
        self.db.set_setting("language", "pt")
        self.db.set_setting("deduction_pct", "5")
        backup.restore_backup(self.db, target)
        self.assertIsNotNone(self.db.get_day(MON))
        self.assertEqual(self.db.get_setting("language"), "pt")  # local setting kept

    def test_unreachable_folder(self):
        blocker = Path(self.dir) / "file"
        blocker.write_text("x")
        with self.assertRaises(backup.BackupError):
            backup.make_backup(self.db, str(blocker / "sub"))


class LicensingTests(unittest.TestCase):
    def _configure(self, key: str):
        salt = "00112233445566778899aabbccddeeff"
        return mock.patch.multiple(
            build_config, KEY_ITERATIONS=1000, KEY_SALT=salt,
            KEY_HASH=licensing.pbkdf2_hex(key, salt, 1000),
        )

    def test_verify_and_bind(self):
        with self._configure("Mistu-Secret-2026"):
            self.assertFalse(licensing.verify_key("wrong"))
            self.assertTrue(licensing.verify_key("  Mistu-Secret-2026 "))
            path = Path(os.environ["MISTU_PROGRAMDATA_DIR"]) / "activation.dat"
            path.unlink(missing_ok=True)
            self.assertEqual(licensing.check_activation(), licensing.Status.NOT_ACTIVATED)
            self.assertFalse(licensing.activate("wrong"))
            self.assertTrue(licensing.activate("Mistu-Secret-2026"))
            self.assertEqual(licensing.check_activation(), licensing.Status.OK)
            with mock.patch.object(licensing, "_raw_machine_id", return_value="other-pc"):
                self.assertEqual(licensing.check_activation(), licensing.Status.WRONG_MACHINE)
        with self._configure("A-new-key-12345"):
            self.assertEqual(licensing.check_activation(), licensing.Status.NOT_ACTIVATED)

    def test_installer_hash_known_value(self):
        import hashlib

        h = hashlib.sha256(b"saltkey").hexdigest()
        h = hashlib.sha256(("salt" + h).encode()).hexdigest()
        self.assertEqual(licensing.installer_hash_hex("key", "salt", 2), h)


if __name__ == "__main__":
    unittest.main()
