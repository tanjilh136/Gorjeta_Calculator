"""Staff: add, edit, archive/restore, delete (only without history), drag to reorder."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import SECTIONS, Database, Staff
from ..i18n import section_name, tr
from .widgets import ask, error, hint_label, page_title

ARCHIVED_BRUSH = QBrush(QColor("#9aa4a8"))


class StaffDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, name: str = "", section: str = "sala"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.name_edit = QLineEdit(name)
        self.name_edit.setMaxLength(60)
        self.section_combo = QComboBox()
        for code in SECTIONS:
            self.section_combo.addItem(section_name(code), code)
        self.section_combo.setCurrentIndex(max(0, self.section_combo.findData(section)))

        form = QFormLayout()
        form.addRow(tr("name") + ":", self.name_edit)
        form.addRow(tr("section") + ":", self.section_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("save"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.name().strip():
            error(self, tr("staff.err.name"))
            return
        self.accept()

    def name(self) -> str:
        return " ".join(self.name_edit.text().split())

    def section(self) -> str:
        return self.section_combo.currentData()


class StaffTree(QTreeWidget):
    orderChanged = Signal()

    def dropEvent(self, event):
        super().dropEvent(event)
        self.orderChanged.emit()


class StaffPage(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db

        self.title = page_title()
        self.hint = hint_label()

        self.tree = StaffTree()
        self.tree.setColumnCount(4)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.invisibleRootItem().setFlags(Qt.ItemIsDropEnabled | Qt.ItemIsEnabled)
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tree.setColumnWidth(0, 50)
        self.tree.setColumnWidth(2, 140)
        self.tree.setColumnWidth(3, 120)
        self.tree.orderChanged.connect(self._save_order)
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        self.tree.itemDoubleClicked.connect(lambda *_: self._edit())

        self.add_btn = QPushButton()
        self.add_btn.setObjectName("primary")
        self.edit_btn = QPushButton()
        self.archive_btn = QPushButton()
        self.delete_btn = QPushButton()
        self.up_btn = QPushButton()
        self.down_btn = QPushButton()
        self.count_label = QLabel()
        self.count_label.setObjectName("hint")

        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.archive_btn.clicked.connect(self._toggle_archive)
        self.delete_btn.clicked.connect(self._delete)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))

        side = QVBoxLayout()
        for b in (self.add_btn, self.edit_btn, self.archive_btn, self.delete_btn):
            side.addWidget(b)
        side.addSpacing(18)
        side.addWidget(self.up_btn)
        side.addWidget(self.down_btn)
        side.addStretch(1)

        body = QHBoxLayout()
        body.addWidget(self.tree, 1)
        body.addLayout(side)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addLayout(body, 1)
        layout.addWidget(self.count_label)

        self.retranslate()

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.title.setText(tr("staff.title"))
        self.hint.setText(tr("staff.hint"))
        self.tree.setHeaderLabels(["#", tr("name"), tr("section"), tr("status")])
        self.add_btn.setText(tr("staff.add"))
        self.edit_btn.setText(tr("staff.edit"))
        self.delete_btn.setText(tr("staff.delete"))
        self.up_btn.setText("▲  " + tr("staff.up"))
        self.down_btn.setText("▼  " + tr("staff.down"))
        self.reload()

    def reload(self, select_id: int | None = None) -> None:
        if select_id is None:
            select_id = self._selected_id()
        self.tree.clear()
        staff = self.db.list_staff()
        for pos, s in enumerate(staff, start=1):
            item = QTreeWidgetItem([str(pos), s.name, section_name(s.section),
                                    tr("active") if s.is_active else tr("archived")])
            item.setData(0, Qt.UserRole, s.id)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            if not s.is_active:
                font = QFont(item.font(1))
                font.setItalic(True)
                for c in range(4):
                    item.setForeground(c, ARCHIVED_BRUSH)
                    item.setFont(c, font)
            self.tree.addTopLevelItem(item)
            if s.id == select_id:
                item.setSelected(True)
                self.tree.setCurrentItem(item)
        active = sum(1 for s in staff if s.is_active)
        self.count_label.setText(tr("staff.count", active=active, archived=len(staff) - active))
        self._update_buttons()

    # ------------------------------------------------------------------
    def _selected_id(self) -> int | None:
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.UserRole) if items else None

    def _selected(self) -> Staff | None:
        sid = self._selected_id()
        return self.db.get_staff(sid) if sid is not None else None

    def _update_buttons(self) -> None:
        s = self._selected()
        has = s is not None
        self.edit_btn.setEnabled(has)
        self.archive_btn.setEnabled(has)
        self.archive_btn.setText(tr("staff.restore") if has and not s.is_active else tr("staff.archive"))
        self.delete_btn.setEnabled(has and not self.db.staff_has_history(s.id))
        idx = self.tree.indexOfTopLevelItem(self.tree.currentItem()) if has else -1
        self.up_btn.setEnabled(has and idx > 0)
        self.down_btn.setEnabled(has and 0 <= idx < self.tree.topLevelItemCount() - 1)

    def _name_taken(self, name: str, except_id: int | None = None) -> bool:
        return any(
            s.name.casefold() == name.casefold() and s.id != except_id for s in self.db.list_staff()
        )

    def _add(self) -> None:
        dlg = StaffDialog(self, tr("staff.dialog.add"))
        while dlg.exec():
            if self._name_taken(dlg.name()):
                error(self, tr("staff.err.duplicate", name=dlg.name()))
                continue
            sid = self.db.add_staff(dlg.name(), dlg.section())
            self.reload(sid)
            self.changed.emit()
            return

    def _edit(self) -> None:
        s = self._selected()
        if s is None:
            return
        dlg = StaffDialog(self, tr("staff.dialog.edit"), s.name, s.section)
        while dlg.exec():
            if self._name_taken(dlg.name(), s.id):
                error(self, tr("staff.err.duplicate", name=dlg.name()))
                continue
            self.db.update_staff(s.id, dlg.name(), dlg.section())
            self.reload(s.id)
            self.changed.emit()
            return

    def _toggle_archive(self) -> None:
        s = self._selected()
        if s is None:
            return
        if s.is_active:
            if not ask(self, tr("staff.confirm.archive", name=s.name)):
                return
        self.db.set_staff_active(s.id, not s.is_active)
        self.reload(s.id)
        self.changed.emit()

    def _delete(self) -> None:
        s = self._selected()
        if s is None:
            return
        if self.db.staff_has_history(s.id):
            error(self, tr("staff.err.history", name=s.name))
            return
        if ask(self, tr("staff.confirm.delete", name=s.name)):
            self.db.delete_staff(s.id)
            self.reload()
            self.changed.emit()

    def _move(self, delta: int) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        idx = self.tree.indexOfTopLevelItem(item)
        new = idx + delta
        if not 0 <= new < self.tree.topLevelItemCount():
            return
        self.tree.takeTopLevelItem(idx)
        self.tree.insertTopLevelItem(new, item)
        self._save_order()

    def _save_order(self) -> None:
        ids = [self.tree.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.tree.topLevelItemCount())]
        self.db.reorder_staff(ids)
        self.reload()
        self.changed.emit()
