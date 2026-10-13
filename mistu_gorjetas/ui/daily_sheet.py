"""Daily Sheet: attendance + cash/card totals for one day, with live split preview."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QObject, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
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
from ..schedule import FERIAS, FOLGA, reasons_for_day
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

COL_NAME, COL_SECTION, COL_CASH, COL_CARD, COL_TOTAL, COL_NOTES = range(6)
N_COLS = 6
GREY = QBrush(QColor("#a3acb0"))
NORMAL = QBrush(QColor("#1b1f21"))
NOTE_ROLE = Qt.UserRole        # the typed note (str)
TAG_ROLE = Qt.UserRole + 1     # FERIAS / FOLGA / None: planned absence label
TAG_COLORS = {FERIAS: QColor("#c0392b"), FOLGA: QColor("#6b777c")}
NOTE_MAX = 200


class NotesDelegate(QStyledItemDelegate):
    """Notes cell: planned-absence label (Férias in red, Folga in grey), the typed
    note, and a pencil icon at the right. Clicking the cell edits the note."""

    PENCIL = "✎"

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        rect = option.rect.adjusted(8, 0, -8, 0)
        painter.save()
        fm = painter.fontMetrics()
        pencil_w = fm.horizontalAdvance(self.PENCIL) + 6
        painter.setPen(QColor("#9aa4a8"))
        painter.drawText(QRect(rect.right() - pencil_w, rect.top(), pencil_w, rect.height()),
                         Qt.AlignRight | Qt.AlignVCenter, self.PENCIL)
        text_rect = rect.adjusted(0, 0, -pencil_w - 4, 0)

        tag = index.data(TAG_ROLE)
        if tag:
            label = tr(f"tag.{tag}")
            bold = QFont(painter.font())
            bold.setBold(True)
            painter.setFont(bold)
            painter.setPen(TAG_COLORS[tag])
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, label)
            used = painter.fontMetrics().horizontalAdvance(label) + 10
            text_rect = text_rect.adjusted(used, 0, 0, 0)
            painter.setFont(option.font)
        note = index.data(NOTE_ROLE) or ""
        if note and text_rect.width() > 10:
            painter.setPen(QColor("#1b1f21"))
            elided = painter.fontMetrics().elidedText(note, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)
        painter.restore()

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setMaxLength(NOTE_MAX)
        editor.setPlaceholderText(tr("daily.note_placeholder"))
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(NOTE_ROLE) or "")

    def setModelData(self, editor, model, index):
        text = " ".join(editor.text().split())
        model.setData(index, text, NOTE_ROLE)
        model.setData(index, text or tr("daily.note_tip"), Qt.ToolTipRole)


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
        self._tags: dict[int, str] = {}  # staff_id -> FERIAS / FOLGA for the shown date
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
        self.table = QTableWidget(0, N_COLS)
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
            self.table.setColumnWidth(c, 110)
        hh.setSectionResizeMode(COL_NOTES, QHeaderView.Stretch)
        self.table.setItemDelegateForColumn(COL_NOTES, NotesDelegate(self.table))
        self.table.cellClicked.connect(self._cell_clicked)
        self.table.itemChanged.connect(self._item_changed)
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
        notes = self._notes()
        old_ids = {s.id for s in self._roster}
        is_new_day = self._day is None
        roster = self._build_roster(self._day)
        self._tags = reasons_for_day(self.db, self._date, [s.id for s in roster])
        present = set()
        for s in roster:
            if s.id in old_ids:
                if s.id in current:
                    present.add(s.id)
            elif is_new_day and s.id not in self._tags:
                present.add(s.id)
        self._roster = roster
        ids = {s.id for s in roster}
        if is_new_day and self._baseline is not None:
            self._baseline = (0, 0, frozenset(i for i in ids if i not in self._tags), frozenset())
        elif self._baseline is not None:
            self._baseline = (self._baseline[0], self._baseline[1],
                              frozenset(i for i in self._baseline[2] if i in ids),
                              frozenset(n for n in self._baseline[3] if n[0] in ids))
        self._fill_table(present, {k: v for k, v in notes.items() if k in ids})
        self._refresh()

    def schedule_changed(self) -> None:
        """Folgas/ferias were edited: a new, untouched day picks up the new defaults;
        otherwise only the labels in the Notes column are refreshed."""
        if self._day is None and not self.is_dirty():
            self._load(self._date)
            return
        self._tags = reasons_for_day(self.db, self._date, [s.id for s in self._roster])
        self._loading = True
        for r, s in enumerate(self._roster):
            item = self.table.item(r, COL_NOTES)
            if item is not None:
                item.setData(TAG_ROLE, self._tags.get(s.id))
        self._loading = False

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
            [tr("daily.present"), tr("section"), tr("cash"), tr("card"), tr("total"), tr("daily.notes")]
        )
        if self._roster:
            self._fill_table(self._present_ids(), self._notes())
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
        self._tags = reasons_for_day(self.db, d, [s.id for s in self._roster])
        if self._day is None:
            # New day: everyone ticked except planned absences (folga / ferias).
            present = {s.id for s in self._roster if s.id not in self._tags}
            notes: dict[int, str] = {}
            self.cash_edit.set_cents(None)
            self.card_edit.set_cents(None)
            self._baseline = (0, 0, frozenset(present), frozenset())
        else:
            ids = {s.id for s in self._roster}
            present = self._day.present_ids
            notes = {k: v for k, v in self._day.notes.items() if k in ids}
            self.cash_edit.set_cents(self._day.cash_total_cents)
            self.card_edit.set_cents(self._day.card_total_cents)
            self._baseline = (
                self._day.cash_total_cents,
                self._day.card_total_cents,
                frozenset(present & ids),
                frozenset(notes.items()),
            )
        self._fill_table(present, notes)
        self._loading = False
        self._refresh()
        self.next_btn.setEnabled(d < date.today())

    def _fill_table(self, present: set[int], notes: dict[int, str]) -> None:
        was_loading = self._loading
        self._loading = True
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
            note_item = QTableWidgetItem()
            note_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            note_item.setData(NOTE_ROLE, notes.get(s.id, ""))
            note_item.setData(TAG_ROLE, self._tags.get(s.id))
            note_item.setToolTip(notes.get(s.id) or tr("daily.note_tip"))
            self.table.setItem(r, COL_NOTES, note_item)
        self._loading = was_loading
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

    def _notes(self) -> dict[int, str]:
        """staff_id -> typed note (non-empty only)."""
        notes = {}
        for r in range(self.table.rowCount()):
            name, item = self.table.item(r, COL_NAME), self.table.item(r, COL_NOTES)
            if name is not None and item is not None and item.data(NOTE_ROLE):
                notes[name.data(Qt.UserRole)] = item.data(NOTE_ROLE)
        return notes

    def _state(self) -> tuple:
        cash, card = self._amounts()
        return (cash, card, frozenset(self._present_ids()), frozenset(self._notes().items()))

    def _cell_clicked(self, row: int, col: int) -> None:
        if col == COL_NOTES:
            self.table.editItem(self.table.item(row, COL_NOTES))
        else:
            self._toggle_row(row)

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == COL_NOTES and not self._loading:
            self._update_status()

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
            for c in range(COL_NOTES):
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
        self.db.save_day(self._date, cash, card, attendance, self._notes())
        self._load(self._date)
        self.dayChanged.emit(self._date)
        return True

    def delete_day(self) -> None:
        """Remove everything saved for the current day (totals, attendance, notes)."""
        if self._day is None:
            return
        if not ask(self, tr("daily.delete_confirm", date=fmt_date(self._date),
                            weekday=weekday_long(self._date))):
            return
        self.db.delete_days(self._date, self._date)
        self._load(self._date)
        self.dayChanged.emit(self._date)
        info(self, tr("daily.deleted", date=fmt_date(self._date)))
