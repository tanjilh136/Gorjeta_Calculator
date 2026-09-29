"""Records & Export: list of saved days, weekly PDF and final PDF."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import pdf_export
from ..db import Database, monday_of
from ..i18n import fmt_date, tr, weekday_short
from ..money import MoneyError, format_euro, format_percent, parse_percent
from ..reports import build_final, build_weekly
from .widgets import (
    WeekBoundEdit,
    ask,
    error,
    hint_label,
    make_readonly_date_edit,
    page_title,
    to_qdate,
)


class RecordsPage(QWidget):
    openDay = Signal(object)  # date

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._last_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

        self.title = page_title()

        # --- saved days list
        self.days_box = QGroupBox()
        self.year_label = QLabel()
        self.year_combo = QComboBox()
        self.year_combo.setMinimumWidth(100)
        self.year_combo.currentIndexChanged.connect(self._fill_days)
        self.open_btn = QPushButton()
        self.open_btn.clicked.connect(self._open_selected)
        top = QHBoxLayout()
        top.addWidget(self.year_label)
        top.addWidget(self.year_combo)
        top.addStretch(1)
        top.addWidget(self.open_btn)

        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._open_row(r))
        self.table.itemSelectionChanged.connect(
            lambda: self.open_btn.setEnabled(bool(self.table.selectedItems()))
        )
        self.days_hint = hint_label()
        self.summary_label = QLabel()
        self.summary_label.setObjectName("summary")

        days_layout = QVBoxLayout(self.days_box)
        days_layout.addLayout(top)
        days_layout.addWidget(self.table, 1)
        days_layout.addWidget(self.summary_label)
        days_layout.addWidget(self.days_hint)

        # --- weekly export
        # Always exactly one week: pick the Monday, the Sunday follows.
        self.weekly_box = QGroupBox()
        self.weekly_start_label = QLabel()
        self.weekly_end_label = QLabel()
        self.weekly_start = WeekBoundEdit(0)
        self.weekly_end = make_readonly_date_edit()
        self.weekly_start.boundChanged.connect(self._update_weekly_end)
        self.weekly_btn = QPushButton()
        self.weekly_btn.setObjectName("primary")
        self.weekly_btn.clicked.connect(self._export_weekly)
        wg = QGridLayout()
        wg.setHorizontalSpacing(10)
        wg.addWidget(self.weekly_start_label, 0, 0)
        wg.addWidget(self.weekly_end_label, 0, 1)
        wg.addWidget(self.weekly_start, 1, 0)
        wg.addWidget(self.weekly_end, 1, 1)
        wl = QVBoxLayout(self.weekly_box)
        wl.addLayout(wg)
        wl.addWidget(self.weekly_btn)

        # --- final export
        self.final_box = QGroupBox()
        self.start_label = QLabel()
        self.end_label = QLabel()
        self.start_edit = WeekBoundEdit(0)
        self.end_edit = WeekBoundEdit(6)
        self.start_edit.boundChanged.connect(lambda _d: self._update_final_label())
        self.end_edit.boundChanged.connect(lambda _d: self._update_final_label())
        self.final_info = QLabel()
        self.final_info.setObjectName("summary")
        self.final_btn = QPushButton()
        self.final_btn.setObjectName("primary")
        self.final_btn.clicked.connect(self._export_final)
        ff = QFormLayout(self.final_box)
        ff.addRow(self.start_label, self.start_edit)
        ff.addRow(self.end_label, self.end_edit)
        ff.addRow(self.final_info)
        ff.addRow(self.final_btn)

        right = QVBoxLayout()
        right.addWidget(self.weekly_box)
        right.addWidget(self.final_box)
        right.addStretch(1)
        right_w = QWidget()
        right_w.setLayout(right)
        right_w.setFixedWidth(390)

        body = QHBoxLayout()
        body.addWidget(self.days_box, 1)
        body.addWidget(right_w)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addLayout(body, 1)

        today = date.today()
        this_monday = monday_of(today)
        self.weekly_start.setMaximumDate(to_qdate(this_monday))
        self.weekly_start.set_value(this_monday - timedelta(days=7))
        self._update_weekly_end(self.weekly_start.value())
        self.start_edit.set_value(this_monday - timedelta(days=28))
        self.end_edit.set_value(this_monday - timedelta(days=1))

        self.retranslate()

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.title.setText(tr("records.title"))
        self.days_box.setTitle(tr("records.saved_days"))
        self.year_label.setText(tr("records.year"))
        self.open_btn.setText(tr("records.open"))
        self.days_hint.setText(tr("records.open_hint"))
        self.table.setHorizontalHeaderLabels(
            [tr("date"), tr("day"), tr("records.present"), tr("cash"), tr("card"), tr("total")]
        )
        self.weekly_box.setTitle(tr("records.weekly"))
        self.weekly_start_label.setText(tr("records.weekly.start"))
        self.weekly_end_label.setText(tr("records.weekly.end"))
        self.weekly_btn.setText(tr("records.weekly.button"))
        self.final_box.setTitle(tr("records.final"))
        self.start_label.setText(tr("records.final.start"))
        self.end_label.setText(tr("records.final.end"))
        self.final_btn.setText(tr("records.final.button"))
        self.reload()

    def reload(self) -> None:
        current = self.year_combo.currentData()
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem(tr("records.all_years"), None)
        for y in self.db.years_with_data():
            self.year_combo.addItem(str(y), y)
        idx = self.year_combo.findData(current)
        self.year_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.year_combo.blockSignals(False)
        self._fill_days()
        self._update_final_label()

    def _fill_days(self) -> None:
        rows = self.db.day_summaries(self.year_combo.currentData())
        self.table.setRowCount(len(rows))
        cash_sum = card_sum = 0
        for r, row in enumerate(rows):
            d = date.fromisoformat(row["date"])
            cash, card = row["cash_total_cents"], row["card_total_cents"]
            cash_sum += cash
            card_sum += card
            values = [fmt_date(d), weekday_short(d), str(row["present_count"]),
                      format_euro(cash), format_euro(card), format_euro(cash + card)]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                if c >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 0:
                    item.setData(Qt.UserRole, d)
                self.table.setItem(r, c, item)
        if rows:
            self.summary_label.setText(tr(
                "records.summary", n=len(rows), cash=format_euro(cash_sum), card=format_euro(card_sum)
            ))
        else:
            self.summary_label.setText(tr("records.no_days"))
        self.open_btn.setEnabled(bool(self.table.selectedItems()))

    def _open_row(self, row: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.openDay.emit(item.data(Qt.UserRole))

    def _open_selected(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        if rows:
            self._open_row(min(rows))

    # ------------------------------------------------------------ exports
    def _deduction_pct(self):
        try:
            return parse_percent(self.db.get_setting("deduction_pct", "0"))
        except MoneyError:
            return parse_percent("0")

    def _update_weekly_end(self, monday: date) -> None:
        self.weekly_end.setDate(to_qdate(monday + timedelta(days=6)))

    def _update_final_label(self) -> None:
        start, end = self.start_edit.value(), self.end_edit.value()
        weeks = ((end - start).days + 1) // 7 if end > start else 0
        self.final_info.setText(tr(
            "records.final.weeks", n=weeks, pct=format_percent(self._deduction_pct())
        ))
        self.final_btn.setEnabled(weeks > 0)

    def _choose_path(self, suggested: str) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("records.save_pdf"), str(Path(self._last_dir) / suggested), "PDF (*.pdf)"
        )
        if not path:
            return None
        p = Path(path)
        if p.suffix.lower() != ".pdf":
            p = p.with_suffix(".pdf")
        self._last_dir = str(p.parent)
        return p

    def _write_pdf(self, render, report, path: Path) -> None:
        try:
            render(report, path)
        except Exception as exc:  # file locked, disk full, ...
            error(self, tr("records.pdf_error", error=exc))
            return
        if ask(self, tr("records.pdf_saved", path=str(path)), title=tr("done"), default_yes=True):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _export_weekly(self) -> None:
        report = build_weekly(self.db, self.weekly_start.value())
        path = self._choose_path(pdf_export.weekly_filename(report))
        if path:
            self._write_pdf(pdf_export.render_weekly, report, path)

    def _export_final(self) -> None:
        start, end = self.start_edit.value(), self.end_edit.value()
        if end <= start:
            error(self, tr("records.final.err_range"))
            return
        report = build_final(self.db, start, end, self._deduction_pct())
        path = self._choose_path(pdf_export.final_filename(report))
        if path:
            self._write_pdf(pdf_export.render_final, report, path)
