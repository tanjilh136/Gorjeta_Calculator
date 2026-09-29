"""Settings: language, deduction %, backup / restore, data retention."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import backup, paths
from ..db import Database, is_valid_database
from ..i18n import LANGUAGES, fmt_date, fmt_datetime, tr
from ..money import MoneyError, parse_percent
from .widgets import ask, error, hint_label, info, make_date_edit, page_title, to_date, to_qdate, warn


class SettingsPage(QWidget):
    languageChanged = Signal(str)
    deductionChanged = Signal()
    dataReplaced = Signal()  # restore / delete: every page must reload

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        # Set by the main window: resolves unsaved Daily Sheet edits before data is replaced.
        self.before_replace = lambda: True
        self.title = page_title()

        # --- general
        self.general_box = QGroupBox()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(db.get_setting("language", "pt"))))
        self.lang_combo.setMaximumWidth(240)
        self.lang_combo.currentIndexChanged.connect(self._language_selected)

        self.ded_label = QLabel()
        self.ded_spin = QDoubleSpinBox()
        self.ded_spin.setRange(0, 100)
        self.ded_spin.setDecimals(2)
        self.ded_spin.setSingleStep(0.5)
        self.ded_spin.setSuffix(" %")
        self.ded_spin.setMaximumWidth(140)
        self.ded_spin.setKeyboardTracking(False)
        try:
            self.ded_spin.setValue(float(parse_percent(db.get_setting("deduction_pct", "0"))))
        except MoneyError:
            self.ded_spin.setValue(0)
        self.ded_spin.valueChanged.connect(self._deduction_changed)
        self.ded_hint = hint_label()

        gf = QFormLayout(self.general_box)
        gf.addRow(self.lang_label, self.lang_combo)
        gf.addRow(self.ded_label, self.ded_spin)
        gf.addRow("", self.ded_hint)

        # --- backup
        self.backup_box = QGroupBox()
        self.folder_label = QLabel()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.browse_btn = QPushButton()
        self.default_btn = QPushButton()
        self.browse_btn.clicked.connect(self._browse)
        self.default_btn.clicked.connect(self._use_default)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_btn)
        folder_row.addWidget(self.default_btn)
        self.backup_hint = hint_label()
        self.last_backup_label = QLabel()
        self.last_backup_label.setObjectName("summary")
        self.backup_now_btn = QPushButton()
        self.backup_now_btn.setObjectName("primary")
        self.restore_btn = QPushButton()
        self.backup_now_btn.clicked.connect(self._backup_now)
        self.restore_btn.clicked.connect(self._restore)
        actions = QHBoxLayout()
        actions.addWidget(self.backup_now_btn)
        actions.addWidget(self.restore_btn)
        actions.addStretch(1)

        bl = QVBoxLayout(self.backup_box)
        fl = QFormLayout()
        fl.addRow(self.folder_label, folder_row)
        bl.addLayout(fl)
        bl.addWidget(self.backup_hint)
        bl.addWidget(self.last_backup_label)
        bl.addLayout(actions)

        # --- retention
        self.retention_box = QGroupBox()
        self.retention_hint = hint_label()
        self.from_label = QLabel()
        self.to_label = QLabel()
        self.del_from = make_date_edit()
        self.del_to = make_date_edit()
        today = date.today()
        self.del_from.setDate(to_qdate(date(today.year - 1, 1, 1)))
        self.del_to.setDate(to_qdate(date(today.year - 1, 12, 31)))
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete_range)
        del_row = QHBoxLayout()
        del_row.addWidget(self.from_label)
        del_row.addWidget(self.del_from)
        del_row.addSpacing(10)
        del_row.addWidget(self.to_label)
        del_row.addWidget(self.del_to)
        del_row.addSpacing(10)
        del_row.addWidget(self.delete_btn)
        del_row.addStretch(1)
        rl = QVBoxLayout(self.retention_box)
        rl.addWidget(self.retention_hint)
        rl.addLayout(del_row)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(28, 22, 28, 22)
        cl.setSpacing(14)
        cl.addWidget(self.title)
        cl.addWidget(self.general_box)
        cl.addWidget(self.backup_box)
        cl.addWidget(self.retention_box)
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
        self.title.setText(tr("settings.title"))
        self.general_box.setTitle(tr("settings.general"))
        self.lang_label.setText(tr("settings.language"))
        self.ded_label.setText(tr("settings.deduction"))
        self.ded_hint.setText(tr("settings.deduction_hint"))
        self.backup_box.setTitle(tr("settings.backup"))
        self.folder_label.setText(tr("settings.backup_folder"))
        self.browse_btn.setText(tr("settings.browse"))
        self.default_btn.setText(tr("settings.reset_default"))
        self.backup_hint.setText(tr("settings.backup_hint", year=date.today().year))
        self.backup_now_btn.setText(tr("settings.backup_now"))
        self.restore_btn.setText(tr("settings.restore"))
        self.retention_box.setTitle(tr("settings.retention"))
        self.retention_hint.setText(tr("settings.retention_hint"))
        self.from_label.setText(tr("settings.delete_from"))
        self.to_label.setText(tr("settings.delete_to"))
        self.delete_btn.setText(tr("settings.delete_button"))
        self.reload()

    def reload(self) -> None:
        self.folder_edit.setText(backup.backup_folder(self.db))
        self.folder_edit.setCursorPosition(0)
        last = self.db.get_setting("last_backup_at")
        when = tr("settings.never")
        if last:
            try:
                when = fmt_datetime(datetime.fromisoformat(last))
            except ValueError:
                pass
        self.last_backup_label.setText(tr("settings.last_backup", when=when))
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(self.db.get_setting("language", "pt"))))
        self.lang_combo.blockSignals(False)
        self.ded_spin.blockSignals(True)
        try:
            self.ded_spin.setValue(float(parse_percent(self.db.get_setting("deduction_pct", "0"))))
        except MoneyError:
            pass
        self.ded_spin.blockSignals(False)

    # ------------------------------------------------------------ general
    def _language_selected(self) -> None:
        code = self.lang_combo.currentData()
        self.db.set_setting("language", code)
        self.languageChanged.emit(code)

    def _deduction_changed(self, value: float) -> None:
        # The spin box holds at most 2 decimals; store it as an exact decimal string.
        pct = Decimal(f"{value:.2f}").normalize()
        self.db.set_setting("deduction_pct", f"{pct:f}")
        self.deductionChanged.emit()

    # ------------------------------------------------------------- backup
    def run_backup(self, parent: QWidget | None = None, quiet: bool = False) -> bool:
        """Backup to the configured folder. Shows a warning (never raises) on failure."""
        folder = backup.backup_folder(self.db)
        try:
            target = backup.make_backup(self.db, folder)
        except backup.BackupError as exc:
            warn(parent or self, tr("settings.backup_fail", folder=folder, error=exc))
            return False
        self.db.set_setting("last_backup_at", datetime.now().isoformat(timespec="seconds"))
        self.reload()
        if not quiet:
            info(parent or self, tr("settings.backup_ok", path=str(target)))
        return True

    def _backup_now(self) -> None:
        self.run_backup()

    def _browse(self) -> None:
        start = self.folder_edit.text()
        if not Path(start).exists():
            start = str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, tr("settings.pick_folder"), start)
        if folder:
            self.db.set_setting("backup_path", str(Path(folder)))
            self.reload()

    def _use_default(self) -> None:
        self.db.set_setting("backup_path", paths.default_backup_dir())
        self.reload()

    def _restore(self) -> None:
        if not self.before_replace():
            return
        start = backup.backup_folder(self.db)
        if not Path(start).exists():
            start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.pick_backup"), start, "Backup (*.db);;* (*)"
        )
        if not path:
            return
        source = Path(path)
        if not is_valid_database(source):
            error(self, tr("settings.restore_invalid"))
            return
        if not ask(self, tr("settings.restore_confirm", path=str(source))):
            return
        try:
            safety = backup.restore_backup(self.db, source)
        except backup.BackupError as exc:
            error(self, tr("settings.restore_fail", error=exc))
            return
        self.reload()
        self.dataReplaced.emit()
        info(self, tr("settings.restore_ok", path=str(safety)))

    # ---------------------------------------------------------- retention
    def _delete_range(self) -> None:
        if not self.before_replace():
            return
        start, end = to_date(self.del_from.date()), to_date(self.del_to.date())
        if end < start:
            error(self, tr("settings.delete_err_range"))
            return
        n = self.db.count_days(start, end)
        if n == 0:
            info(self, tr("settings.delete_none", start=fmt_date(start), end=fmt_date(end)),
                 title=tr("settings.retention"))
            return
        if not ask(self, tr("settings.delete_confirm", n=n, start=fmt_date(start), end=fmt_date(end))):
            return
        folder = backup.backup_folder(self.db)
        try:
            backup.make_backup(self.db, folder)
            self.db.set_setting("last_backup_at", datetime.now().isoformat(timespec="seconds"))
        except backup.BackupError as exc:
            error(self, tr("settings.delete_backup_fail", error=f"{folder}\n{exc}"))
            return
        deleted = self.db.delete_days(start, end)
        self.reload()
        self.dataReplaced.emit()
        info(self, tr("settings.delete_ok", n=deleted))

