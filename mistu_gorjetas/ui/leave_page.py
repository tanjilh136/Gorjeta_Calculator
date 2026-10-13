"""Folgas e Férias: weekly days off per person and scheduled holidays."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import Database, Ferias
from ..i18n import WEEKDAYS_SHORT, fmt_date, language, tr
from .widgets import ask, error, hint_label, make_date_edit, page_title, to_date, to_qdate

PAST_BRUSH = QBrush(QColor("#9aa4a8"))
ONGOING_BRUSH = QBrush(QColor("#c0392b"))


class FeriasDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, staff: list, current: Ferias | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.staff_combo = QComboBox()
        for s in staff:
            self.staff_combo.addItem(s.name, s.id)
        self.start_edit = make_date_edit()
        self.end_edit = make_date_edit()
        self.days_label = QLabel()
        self.days_label.setObjectName("hint")
        today = date.today()
        if current is not None:
            self.staff_combo.setCurrentIndex(max(0, self.staff_combo.findData(current.staff_id)))
            self.start_edit.setDate(to_qdate(current.start))
            self.end_edit.setDate(to_qdate(current.end))
        else:
            self.start_edit.setDate(to_qdate(today))
            self.end_edit.setDate(to_qdate(today))
        self.start_edit.dateChanged.connect(self._start_changed)
        self.end_edit.dateChanged.connect(self._update_days)

        form = QFormLayout()
        form.addRow(tr("staff") + ":", self.staff_combo)
        form.addRow(tr("leave.start") + ":", self.start_edit)
        form.addRow(tr("leave.end") + ":", self.end_edit)
        form.addRow("", self.days_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("save"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_days()

    def _start_changed(self) -> None:
        # Moving the start past the end drags the end along.
        if self.end() < self.start():
            self.end_edit.setDate(self.start_edit.date())
        self._update_days()

    def _update_days(self) -> None:
        n = (self.end() - self.start()).days + 1
        self.days_label.setText(tr("leave.one_day") if n == 1 else tr("leave.n_days", n=max(n, 0)))

    def _accept(self) -> None:
        if self.end() < self.start():
            error(self, tr("leave.err.range"))
            return
        self.accept()

    def staff_id(self) -> int:
        return self.staff_combo.currentData()

    def start(self) -> date:
        return to_date(self.start_edit.date())

    def end(self) -> date:
        return to_date(self.end_edit.date())


class LeavePage(QWidget):
    changed = Signal()  # folgas or ferias were edited

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._filling = False
        self.title = page_title()

        # --- folgas grid: staff x weekdays
        self.folgas_box = QGroupBox()
        self.folgas_hint = hint_label()
        self.grid = QTableWidget(0, 8)
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.setFocusPolicy(Qt.NoFocus)
        self.grid.verticalHeader().setVisible(False)
        self.grid.setAlternatingRowColors(True)
        self.grid.setShowGrid(False)
        gh = self.grid.horizontalHeader()
        gh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 8):
            gh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.grid.setColumnWidth(c, 64)
        self.grid.cellClicked.connect(self._toggle_folga)
        fl = QVBoxLayout(self.folgas_box)
        fl.addWidget(self.folgas_hint)
        fl.addWidget(self.grid)

        # --- ferias list
        self.ferias_box = QGroupBox()
        self.ferias_hint = hint_label()
        self.add_btn = QPushButton()
        self.add_btn.setObjectName("primary")
        self.edit_btn = QPushButton()
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("danger")
        self.show_past = QCheckBox()
        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn.clicked.connect(self._delete)
        self.show_past.toggled.connect(self._fill_ferias)
        bar = QHBoxLayout()
        bar.addWidget(self.add_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addStretch(1)
        bar.addWidget(self.show_past)

        self.ferias_table = QTableWidget(0, 5)
        self.ferias_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ferias_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ferias_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ferias_table.verticalHeader().setVisible(False)
        self.ferias_table.setAlternatingRowColors(True)
        self.ferias_table.setShowGrid(False)
        self.ferias_table.setMinimumHeight(200)
        fh = self.ferias_table.horizontalHeader()
        fh.setSectionResizeMode(QHeaderView.Stretch)
        self.ferias_table.itemSelectionChanged.connect(self._update_buttons)
        self.ferias_table.cellDoubleClicked.connect(lambda *_: self._edit())
        vl = QVBoxLayout(self.ferias_box)
        vl.addWidget(self.ferias_hint)
        vl.addLayout(bar)
        vl.addWidget(self.ferias_table)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(28, 22, 28, 22)
        cl.setSpacing(14)
        cl.addWidget(self.title)
        cl.addWidget(self.folgas_box)
        cl.addWidget(self.ferias_box)
        cl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.retranslate()

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.title.setText(tr("leave.title"))
        self.folgas_box.setTitle(tr("leave.folgas"))
        self.folgas_hint.setText(tr("leave.folgas_hint"))
        self.grid.setHorizontalHeaderLabels([tr("staff")] + WEEKDAYS_SHORT[language()])
        self.ferias_box.setTitle(tr("leave.ferias"))
        self.ferias_hint.setText(tr("leave.ferias_hint"))
        self.add_btn.setText(tr("leave.add"))
        self.edit_btn.setText(tr("leave.edit"))
        self.delete_btn.setText(tr("leave.delete"))
        self.show_past.setText(tr("leave.show_past"))
        self.ferias_table.setHorizontalHeaderLabels(
            [tr("staff"), tr("leave.start"), tr("leave.end"), tr("leave.days"), tr("status")]
        )
        self.reload()

    def reload(self) -> None:
        self._fill_folgas()
        self._fill_ferias()

    # ------------------------------------------------------------- folgas
    def _fill_folgas(self) -> None:
        self._filling = True
        staff = self.db.list_staff(active_only=True)
        folgas = self.db.get_folgas()
        self.grid.setRowCount(len(staff))
        for r, s in enumerate(staff):
            name = QTableWidgetItem(s.name)
            name.setData(Qt.UserRole, s.id)
            self.grid.setItem(r, 0, name)
            for wd in range(7):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled)  # toggled by clicking anywhere in the cell
                item.setCheckState(Qt.Checked if wd in folgas.get(s.id, ()) else Qt.Unchecked)
                self.grid.setItem(r, wd + 1, item)
        rows_h = sum(self.grid.rowHeight(r) for r in range(len(staff)))
        self.grid.setFixedHeight(min(360, self.grid.horizontalHeader().height() + rows_h + 6))
        self._filling = False

    def _toggle_folga(self, row: int, col: int) -> None:
        if col == 0 or self._filling:
            return
        item = self.grid.item(row, col)
        on = item.checkState() != Qt.Checked
        item.setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.db.set_folga(self.grid.item(row, 0).data(Qt.UserRole), col - 1, on)
        self.changed.emit()

    # ------------------------------------------------------------- ferias
    def _fill_ferias(self) -> None:
        names = {s.id: s.name for s in self.db.list_staff()}
        today = date.today()
        rows = [f for f in self.db.list_ferias() if self.show_past.isChecked() or f.end >= today]
        # Current and planned first (soonest first), then finished ones (most recent first).
        rows.sort(key=lambda f: (f.end < today, f.start.toordinal() * (1 if f.end >= today else -1)))
        self.ferias_table.setRowCount(len(rows))
        for r, f in enumerate(rows):
            if f.end < today:
                state, brush = tr("leave.state.finished"), PAST_BRUSH
            elif f.start <= today:
                state, brush = tr("leave.state.ongoing"), ONGOING_BRUSH
            else:
                state, brush = tr("leave.state.planned"), None
            values = [names.get(f.staff_id, "?"), fmt_date(f.start), fmt_date(f.end),
                      str((f.end - f.start).days + 1), state]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                if c == 0:
                    item.setData(Qt.UserRole, f.id)
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if brush is not None:
                    item.setForeground(brush)
                self.ferias_table.setItem(r, c, item)
        self._update_buttons()

    def _selected(self) -> Ferias | None:
        items = self.ferias_table.selectedItems()
        if not items:
            return None
        fid = self.ferias_table.item(items[0].row(), 0).data(Qt.UserRole)
        return next((f for f in self.db.list_ferias() if f.id == fid), None)

    def _update_buttons(self) -> None:
        has = bool(self.ferias_table.selectedItems())
        self.edit_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _dialog_staff(self, include_id: int | None = None) -> list:
        return [s for s in self.db.list_staff() if s.is_active or s.id == include_id]

    def _save_dialog(self, dlg: FeriasDialog, ferias_id: int | None) -> bool:
        clash = self.db.ferias_conflict(dlg.staff_id(), dlg.start(), dlg.end(), exclude_id=ferias_id)
        if clash is not None:
            error(self, tr("leave.err.overlap", name=dlg.staff_combo.currentText(),
                           start=fmt_date(clash.start), end=fmt_date(clash.end)))
            return False
        if ferias_id is None:
            self.db.add_ferias(dlg.staff_id(), dlg.start(), dlg.end())
        else:
            self.db.update_ferias(ferias_id, dlg.staff_id(), dlg.start(), dlg.end())
        self._fill_ferias()
        self.changed.emit()
        return True

    def _add(self) -> None:
        staff = self._dialog_staff()
        if not staff:
            error(self, tr("leave.err.no_staff"))
            return
        dlg = FeriasDialog(self, tr("leave.dialog.add"), staff)
        while dlg.exec():
            if self._save_dialog(dlg, None):
                return

    def _edit(self) -> None:
        f = self._selected()
        if f is None:
            return
        dlg = FeriasDialog(self, tr("leave.dialog.edit"), self._dialog_staff(f.staff_id), f)
        while dlg.exec():
            if self._save_dialog(dlg, f.id):
                return

    def _delete(self) -> None:
        f = self._selected()
        if f is None:
            return
        name = self.db.get_staff(f.staff_id).name if self.db.get_staff(f.staff_id) else "?"
        if ask(self, tr("leave.confirm.delete", name=name, start=fmt_date(f.start), end=fmt_date(f.end))):
            self.db.delete_ferias(f.id)
            self._fill_ferias()
            self.changed.emit()
