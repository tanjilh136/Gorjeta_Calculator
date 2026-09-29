"""Daily Sheet: attendance + cash/card totals for one day, with live split preview."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import Database, Day, Staff, retention_cutoff
from ..i18n import fmt_date, fmt_datetime, section_name, tr, weekday_long
from ..money import MoneyError, format_euro, split_equally
from .widgets import (
    MoneyEdit,
    ask,
    ask_save,
    error,
    info,
    make_date_edit,
    page_title,
    to_date,
    to_qdate,
)

COL_NAME, COL_SECTION, COL_CASH, COL_CARD, COL_TOTAL = range(5)
GREY = QBrush(QColor("#a3acb0"))
NORMAL = QBrush(QColor("#1b1f21"))


class _SpaceToggle(QObject):
    """Space bar toggles the current row's checkbox."""

    def __init__(self, page: "DailySheetPage"):
        super().__init__(page)
        self._page = page

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Space:
            row = self._page.table.currentRow()
            if row >= 0:
                self._page._toggle_row(row)
                return True
        return False


class DailySheetPage(QWidget):
    dayChanged = Signal(object)  # date that was saved or deleted

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._date: date = date.today()
        self._roster: list[Staff] = []
        self._day: Day | None = None
        self._baseline: tuple | None = None
        self._loading = False

        self.title = page_title()

        # --- date bar
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("iconButton")
        self.next_btn = QPushButton("▶")
        self.next_btn.setObjectName("iconButton")
        self.date_edit = make_date_edit()
        self.date_edit.setObjectName("bigDate")
        self.today_btn = QPushButton()
        self.weekday_label = QLabel()
        self.weekday_label.setObjectName("weekday")
        self.status_label = QLabel()
        self.status_label.setObjectName("status")

        date_bar = QHBoxLayout()
        date_bar.addWidget(self.prev_btn)
        date_bar.addWidget(self.date_edit)
        date_bar.addWidget(self.next_btn)
        date_bar.addWidget(self.today_btn)
        date_bar.addSpacing(12)
        date_bar.addWidget(self.weekday_label)
        date_bar.addStretch(1)
        date_bar.addWidget(self.status_label)

        # --- amounts
        self.cash_edit = MoneyEdit()
        self.card_edit = MoneyEdit()
        for e in (self.cash_edit, self.card_edit):
            e.setObjectName("amount")
            e.setMaximumWidth(200)
        self.cash_label = QLabel()
        self.card_label = QLabel()
        amounts = QFormLayout()
        amounts.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        amounts.addRow(self.cash_label, self.cash_edit)
        amounts.addRow(self.card_label, self.card_edit)

        self.count_label = QLabel()
        self.count_label.setObjectName("summaryStrong")
        self.share_label = QLabel()
        self.share_label.setObjectName("summary")
        self.share_label.setWordWrap(True)
        summary = QVBoxLayout()
        summary.addWidget(self.count_label)
        summary.addWidget(self.share_label)
        summary.addStretch(1)

        amounts_card = QFrame()
        amounts_card.setObjectName("card")
        amounts_row = QHBoxLayout(amounts_card)
        amounts_row.addLayout(amounts)
        amounts_row.addSpacing(30)
        amounts_row.addLayout(summary, 1)

        # --- staff table
        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.StrongFocus)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for c in (COL_SECTION, COL_CASH, COL_CARD, COL_TOTAL):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.table.setColumnWidth(c, 120)
        self.table.cellClicked.connect(lambda r, _c: self._toggle_row(r))
        self.table.installEventFilter(_SpaceToggle(self))

        self.empty_label = QLabel()
        self.empty_label.setObjectName("hint")
        self.empty_label.setAlignment(Qt.AlignCenter)

        # --- bottom buttons
        self.all_btn = QPushButton()
        self.none_btn = QPushButton()
        self.revert_btn = QPushButton()
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("danger")
        self.save_btn = QPushButton()
        self.save_btn.setObjectName("primary")
        self.save_btn.setMinimumWidth(160)
        buttons = QHBoxLayout()
        buttons.addWidget(self.all_btn)
        buttons.addWidget(self.none_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.delete_btn)
        buttons.addSpacing(16)
        buttons.addWidget(self.revert_btn)
        buttons.addWidget(self.save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addLayout(date_bar)
        layout.addWidget(amounts_card)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_label)
        layout.addLayout(buttons)

        # --- signals
        self.prev_btn.clicked.connect(lambda: self.open_date(self._date - timedelta(days=1)))
        self.next_btn.clicked.connect(lambda: self.open_date(self._date + timedelta(days=1)))
        self.today_btn.clicked.connect(lambda: self.open_date(date.today()))
        self.date_edit.dateChanged.connect(self._on_date_edited)
        self.cash_edit.textChanged.connect(self._refresh)
        self.card_edit.textChanged.connect(self._refresh)
        self.all_btn.clicked.connect(lambda: self._set_all(True))
        self.none_btn.clicked.connect(lambda: self._set_all(False))
        self.revert_btn.clicked.connect(lambda: self._load(self._date))
        self.save_btn.clicked.connect(self.save)
        self.delete_btn.clicked.connect(self.delete_day)
        QShortcut(QKeySequence.Save, self, activated=self.save)

        self._update_date_limits()
        self.retranslate()
        self._load(date.today())

    # ------------------------------------------------------------ public
    def current_date(self) -> date:
        return self._date

    def is_dirty(self) -> bool:
        return self._baseline is not None and self._state() != self._baseline

    def open_date(self, d: date) -> bool:
        """Switch to another day, asking about unsaved changes first."""
        d = min(d, date.today())
        if d == self._date:
            self._sync_date_edit()
            return True
        if not self.maybe_save():
            self._sync_date_edit()
            return False
        self._load(d)
        return True

    def maybe_save(self) -> bool:
        """True if it is OK to leave the current day (saved, discarded or clean)."""
        if not self.is_dirty():
            return True
        res = ask_save(self, tr("daily.unsaved_q", date=fmt_date(self._date)))
        if res == QMessageBox.Save:
            return self.save()
        return res == QMessageBox.Discard

    def reload_staff(self) -> None:
        """Staff list changed (added, archived, reordered): rebuild rows, keep edits."""
        current = self._present_ids()
        old_ids = {s.id for s in self._roster}
        is_new_day = self._day is None
        roster = self._build_roster(self._day)
        present = set()
        for s in roster:
            if s.id in old_ids:
                if s.id in current:
                    present.add(s.id)
            elif is_new_day:
                present.add(s.id)
        self._roster = roster
        if is_new_day and self._baseline is not None:
            self._baseline = (0, 0, frozenset(s.id for s in roster))
        elif self._baseline is not None:
            self._baseline = (self._baseline[0], self._baseline[1],
                              frozenset(i for i in self._baseline[2] if i in {s.id for s in roster}))
        self._fill_table(present)
        self._refresh()

    def reload(self) -> None:
        """Data changed underneath (restore, delete): reload the current day."""
        self._update_date_limits()
        self._load(min(self._date, date.today()))

    def retranslate(self) -> None:
        self.title.setText(tr("daily.title"))
        self.prev_btn.setToolTip(tr("daily.prev"))
        self.next_btn.setToolTip(tr("daily.next"))
        self.today_btn.setText(tr("daily.today"))
        self.cash_label.setText(tr("daily.cash_total"))
        self.card_label.setText(tr("daily.card_total"))
        self.all_btn.setText(tr("daily.select_all"))
        self.none_btn.setText(tr("daily.select_none"))
        self.revert_btn.setText(tr("daily.revert"))
        self.delete_btn.setText(tr("daily.delete"))
        self.save_btn.setText(tr("save") + "  (Ctrl+S)")
        self.empty_label.setText(tr("daily.no_staff"))
        self.table.setHorizontalHeaderLabels(
            [tr("daily.present"), tr("section"), tr("cash"), tr("card"), tr("total")]
        )
        if self._roster:
            self._fill_table(self._present_ids())
        self._refresh()

    # ----------------------------------------------------------- loading
    def _update_date_limits(self) -> None:
        self.date_edit.blockSignals(True)
        self.date_edit.setMaximumDate(to_qdate(date.today()))
        self.date_edit.setMinimumDate(to_qdate(retention_cutoff(date.today())))
        self.date_edit.blockSignals(False)

    def _sync_date_edit(self) -> None:
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(to_qdate(self._date))
        self.date_edit.blockSignals(False)

    def _on_date_edited(self, qd) -> None:
        self.open_date(to_date(qd))

    def _build_roster(self, day: Day | None) -> list[Staff]:
        stored_present = day.present_ids if day else set()
        return [s for s in self.db.list_staff() if s.is_active or s.id in stored_present]

    def _load(self, d: date) -> None:
        self._update_date_limits()
        self._loading = True
        self._date = d
        self._sync_date_edit()
        self._day = self.db.get_day(d)
        self._roster = self._build_roster(self._day)
        if self._day is None:
            present = {s.id for s in self._roster}
            self.cash_edit.set_cents(None)
            self.card_edit.set_cents(None)
            self._baseline = (0, 0, frozenset(present))
        else:
            present = self._day.present_ids
            self.cash_edit.set_cents(self._day.cash_total_cents)
            self.card_edit.set_cents(self._day.card_total_cents)
            self._baseline = (
                self._day.cash_total_cents,
                self._day.card_total_cents,
                frozenset(present & {s.id for s in self._roster}),
            )
        self._fill_table(present)
        self._loading = False
        self._refresh()
        self.next_btn.setEnabled(d < date.today())

    def _fill_table(self, present: set[int]) -> None:
        self.table.setRowCount(len(self._roster))
        for r, s in enumerate(self._roster):
            name = s.name if s.is_active else f"{s.name}  {tr('daily.archived_tag')}"
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setCheckState(Qt.Checked if s.id in present else Qt.Unchecked)
            name_item.setData(Qt.UserRole, s.id)
            self.table.setItem(r, COL_NAME, name_item)
            self.table.setItem(r, COL_SECTION, QTableWidgetItem(section_name(s.section)))
            for c in (COL_CASH, COL_CARD, COL_TOTAL):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        has_rows = bool(self._roster)
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

    # ------------------------------------------------------------- state
    def _present_ids(self) -> set[int]:
        ids = set()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, COL_NAME)
            if item is not None and item.checkState() == Qt.Checked:
                ids.add(item.data(Qt.UserRole))
        return ids

    def _amounts(self) -> tuple[int | None, int | None]:
        def get(edit: MoneyEdit):
            try:
                return edit.cents()
            except MoneyError:
                return None
        return get(self.cash_edit), get(self.card_edit)

    def _state(self) -> tuple:
        cash, card = self._amounts()
        return (cash, card, frozenset(self._present_ids()))

    def _toggle_row(self, row: int) -> None:
        item = self.table.item(row, COL_NAME)
        if item is None:
            return
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        self._refresh()

    def _set_all(self, checked: bool) -> None:
        for r in range(self.table.rowCount()):
            self.table.item(r, COL_NAME).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._refresh()

    def _refresh(self) -> None:
        if self._loading:
            return
        present = self._present_ids()
        n = len(present)
        cash, card = self._amounts()
        cash_share = split_equally(cash, n) if cash is not None else None
        card_share = split_equally(card, n) if card is not None else None

        for r in range(self.table.rowCount()):
            item = self.table.item(r, COL_NAME)
            is_present = item.checkState() == Qt.Checked
            brush = NORMAL if is_present else GREY
            values = ("–", "–", "–")
            if is_present and cash_share is not None and card_share is not None:
                values = (format_euro(cash_share), format_euro(card_share),
                          format_euro(cash_share + card_share))
            for c, v in zip((COL_CASH, COL_CARD, COL_TOTAL), values):
                self.table.item(r, c).setText(v)
            for c in range(5):
                self.table.item(r, c).setForeground(brush)

        self.count_label.setText(tr("daily.present_count", n=n, total=len(self._roster)))
        if n and cash_share is not None and card_share is not None:
            self.share_label.setText(tr(
                "daily.per_person", cash=format_euro(cash_share), card=format_euro(card_share),
                total=format_euro(cash_share + card_share),
            ))
        else:
            self.share_label.setText("")

        self.weekday_label.setText(weekday_long(self._date))
        self._update_status()

    def _update_status(self) -> None:
        dirty = self.is_dirty()
        if self._day is None and not dirty:
            text, state = tr("daily.status.new"), "new"
        elif dirty:
            text, state = tr("daily.status.unsaved"), "unsaved"
        else:
            try:
                when = fmt_datetime(datetime.fromisoformat(self._day.updated_at))
                text = tr("daily.status.saved_at", when=when)
            except (ValueError, TypeError):
                text = tr("daily.status.saved")
            state = "saved"
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.save_btn.setEnabled(bool(self._roster) or self._day is not None)
        self.revert_btn.setEnabled(dirty)
        self.delete_btn.setEnabled(self._day is not None)

    # -------------------------------------------------------------- save
    def save(self) -> bool:
        try:
            cash = self.cash_edit.cents()
        except MoneyError:
            error(self, tr("daily.err.amount", field=tr("daily.cash_total")))
            self.cash_edit.setFocus()
            return False
        try:
            card = self.card_edit.cents()
        except MoneyError:
            error(self, tr("daily.err.amount", field=tr("daily.card_total")))
            self.card_edit.setFocus()
            return False

        present = self._present_ids()
        if (cash > 0 or card > 0) and not present:
            error(self, tr("daily.err.nobody"))
            return False

        attendance = {s.id: s.id in present for s in self._roster}
        self.db.save_day(self._date, cash, card, attendance)
        self._load(self._date)
        self.dayChanged.emit(self._date)
        return True

    def delete_day(self) -> None:
        """Remove everything saved for the current day (totals and attendance)."""
        if self._day is None:
            return
        if not ask(self, tr("daily.delete_confirm", date=fmt_date(self._date),
                            weekday=weekday_long(self._date))):
            return
        self.db.delete_days(self._date, self._date)
        self._load(self._date)
        self.dayChanged.emit(self._date)
        info(self, tr("daily.deleted", date=fmt_date(self._date)))
