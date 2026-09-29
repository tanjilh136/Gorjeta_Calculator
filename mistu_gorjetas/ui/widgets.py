"""Shared widgets and helpers."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QEvent, QObject, QRegularExpression, Qt, Signal
from PySide6.QtGui import QColor, QRegularExpressionValidator, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCalendarWidget,
    QDateEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableView,
    QWidget,
)

from ..i18n import tr
from ..money import MoneyError, format_amount, parse_amount


def to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def to_date(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def page_title(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageTitle")
    return label


def hint_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label


# ------------------------------------------------------------- messages
def _box(parent, icon, title, text, buttons, default) -> QMessageBox.StandardButton:
    box = QMessageBox(icon, title, text, buttons, parent)
    names = {
        QMessageBox.Yes: tr("yes"), QMessageBox.No: tr("no"), QMessageBox.Ok: tr("ok"),
        QMessageBox.Cancel: tr("cancel"), QMessageBox.Save: tr("save"),
        QMessageBox.Discard: tr("discard"),
    }
    for std, name in names.items():
        b = box.button(std)
        if b is not None:
            b.setText(name)
    if default is not None:
        box.setDefaultButton(default)
    return QMessageBox.StandardButton(box.exec())


def info(parent, text: str, title: str | None = None) -> None:
    _box(parent, QMessageBox.Information, title or tr("done"), text, QMessageBox.Ok, None)


def warn(parent, text: str, title: str | None = None) -> None:
    _box(parent, QMessageBox.Warning, title or tr("warning"), text, QMessageBox.Ok, None)


def error(parent, text: str, title: str | None = None) -> None:
    _box(parent, QMessageBox.Critical, title or tr("error"), text, QMessageBox.Ok, None)


def ask(parent, text: str, title: str | None = None, default_yes: bool = False) -> bool:
    res = _box(
        parent, QMessageBox.Question, title or tr("confirm"), text,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes if default_yes else QMessageBox.No,
    )
    return res == QMessageBox.Yes


def ask_save(parent, text: str) -> QMessageBox.StandardButton:
    """Returns Save, Discard or Cancel."""
    return _box(
        parent, QMessageBox.Warning, tr("confirm"), text,
        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save,
    )


# ------------------------------------------------------------ MoneyEdit
class MoneyEdit(QLineEdit):
    """Euro amount input. Accepts 1.234,56 / 1234,56 / 1234.56 and reformats on leaving."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9.,€ ]{0,16}"), self))
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setPlaceholderText("0,00")
        self.textChanged.connect(self._update_valid)

    def cents(self) -> int:
        """Raises MoneyError if the text is not a valid amount."""
        return parse_amount(self.text())

    def is_valid(self) -> bool:
        try:
            self.cents()
            return True
        except MoneyError:
            return False

    def set_cents(self, cents: int | None) -> None:
        self.setText("" if cents is None else format_amount(cents))

    def _update_valid(self) -> None:
        self.setProperty("invalid", not self.is_valid())
        self.style().unpolish(self)
        self.style().polish(self)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if self.text().strip() and self.is_valid():
            self.blockSignals(True)
            self.set_cents(self.cents())
            self.blockSignals(False)
            self._update_valid()


# ------------------------------------------------------------ date edits
def make_date_edit(parent: QWidget | None = None) -> QDateEdit:
    edit = QDateEdit(parent)
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("dd/MM/yyyy")
    edit.calendarWidget().setFirstDayOfWeek(Qt.Monday)
    edit.calendarWidget().setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    edit.setKeyboardTracking(False)
    edit.setMinimumWidth(130)
    return edit


def make_readonly_date_edit(parent: QWidget | None = None) -> QDateEdit:
    """Looks like a date field but only displays a computed date."""
    edit = QDateEdit(parent)
    edit.setDisplayFormat("dd/MM/yyyy")
    edit.setReadOnly(True)
    edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
    edit.setFocusPolicy(Qt.NoFocus)
    edit.setObjectName("readonlyDate")
    edit.setMinimumWidth(130)
    return edit


class _WeekdayClickFilter(QObject):
    """Swallows mouse clicks on calendar cells that are not the allowed weekday.

    The calendar has no vertical header and weeks start on Monday, so the cell
    column is the weekday (0 = Monday ... 6 = Sunday)."""

    def __init__(self, view: QTableView, weekday: int):
        super().__init__(view)
        self._view = view
        self._weekday = weekday

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                            QEvent.MouseButtonDblClick, QEvent.MouseMove):
            index = self._view.indexAt(event.position().toPoint())
            if index.isValid() and index.column() != self._weekday:
                return True
        return False


class WeekBoundEdit(QDateEdit):
    """Date edit that only accepts Mondays (start) or Sundays (end).

    In the calendar popup only that weekday can be clicked; the other days are
    greyed out. Keyboard changes are snapped to the allowed weekday."""

    boundChanged = Signal(object)  # python date

    def __init__(self, weekday: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._weekday = weekday  # 0 = Monday, 6 = Sunday
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setKeyboardTracking(False)
        self.setMinimumWidth(130)
        cal = self.calendarWidget()
        cal.setFirstDayOfWeek(Qt.Monday)
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setMinimumWidth(300)
        self._paint_page(cal.yearShown(), cal.monthShown())
        cal.currentPageChanged.connect(self._paint_page)
        view = cal.findChild(QTableView)
        if view is not None:
            view.viewport().installEventFilter(_WeekdayClickFilter(view, weekday))
        self._last = to_date(self.date())
        self.dateChanged.connect(self._snap)

    def _paint_page(self, year: int, month: int) -> None:
        """Grey out every day of the visible grid (incl. the neighbouring months'
        days) except the allowed weekday."""
        cal = self.calendarWidget()
        disabled = QTextCharFormat()
        disabled.setForeground(QColor("#c3c9cc"))
        allowed = QTextCharFormat()
        allowed.setForeground(QColor("#0f5d6e"))
        allowed.setFontWeight(700)
        cal.setDateTextFormat(QDate(), QTextCharFormat())  # clear previous page
        first = date(year, month, 1)
        start = first - timedelta(days=first.weekday() + 7)
        for i in range(56):
            d = start + timedelta(days=i)
            cal.setDateTextFormat(to_qdate(d), allowed if d.weekday() == self._weekday else disabled)

    def value(self) -> date:
        return to_date(self.date())

    def set_value(self, d: date) -> None:
        self._last = d
        self.setDate(to_qdate(d))

    def _snap(self, qd: QDate) -> None:
        d = to_date(qd)
        if d.weekday() != self._weekday:
            step = (d - self._last).days
            if self._weekday == 0:
                # Arrow-up from a Monday moves to the next Monday, otherwise go to
                # the Monday of the chosen week.
                target = self._last + timedelta(days=7) if step == 1 else d - timedelta(days=d.weekday())
            else:
                target = self._last - timedelta(days=7) if step == -1 else d + timedelta(days=6 - d.weekday())
            self._last = target
            self.setDate(to_qdate(target))  # re-enters _snap with a valid date
            return
        self._last = d
        self.boundChanged.emit(d)
