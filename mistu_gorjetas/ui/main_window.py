"""Main window: left sidebar navigation + stacked pages."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, CREDIT, VERSION, i18n
from ..db import Database
from ..i18n import tr
from .about_page import AboutPage
from .daily_sheet import DailySheetPage
from .leave_page import LeavePage
from .records_page import RecordsPage
from .settings_page import SettingsPage
from .staff_page import StaffPage

log = logging.getLogger(__name__)

NAV_KEYS = ["nav.daily", "nav.staff", "nav.leave", "nav.records", "nav.settings", "nav.about"]
DAILY, STAFF, LEAVE, RECORDS, SETTINGS, ABOUT = range(6)


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self.setMinimumSize(980, 620)

        # --- sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        title = QLabel(APP_NAME)
        title.setObjectName("sidebarTitle")
        sub = QLabel(f"v{VERSION}")
        sub.setObjectName("sidebarSub")
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFocusPolicy(Qt.NoFocus)
        for _ in NAV_KEYS:
            self.nav.addItem(QListWidgetItem())
        credit = QLabel(CREDIT)
        credit.setObjectName("sidebarCredit")
        credit.setWordWrap(True)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        sl.addWidget(title)
        sl.addWidget(sub)
        sl.addWidget(self.nav, 1)
        sl.addWidget(credit)

        # --- pages
        self.daily = DailySheetPage(db)
        self.staff = StaffPage(db)
        self.leave = LeavePage(db)
        self.records = RecordsPage(db)
        self.settings = SettingsPage(db)
        self.about = AboutPage()
        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        for page in (self.daily, self.staff, self.leave, self.records, self.settings, self.about):
            self.stack.addWidget(page)

        central = QWidget()
        cl = QHBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(sidebar)
        cl.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # --- wiring
        self.nav.currentRowChanged.connect(self._navigate)
        self.staff.changed.connect(self._staff_changed)
        self.leave.changed.connect(self.daily.schedule_changed)
        self.daily.dayChanged.connect(lambda _d: self.records.reload())
        self.records.openDay.connect(self._open_day)
        self.settings.languageChanged.connect(self._language_changed)
        self.settings.deductionChanged.connect(self.records.reload)
        self.settings.dataReplaced.connect(self._data_replaced)
        self.settings.before_replace = self.daily.maybe_save

        self._retranslate_nav()
        self.nav.setCurrentRow(DAILY)

    # ------------------------------------------------------------------
    def _navigate(self, row: int) -> None:
        if row < 0:
            return
        if row == RECORDS:
            self.records.reload()
        self.stack.setCurrentIndex(row)

    def _open_day(self, d) -> None:
        self.nav.setCurrentRow(DAILY)
        self.daily.open_date(d)

    def _staff_changed(self) -> None:
        self.daily.reload_staff()
        self.leave.reload()
        self.records.reload()

    def _data_replaced(self) -> None:
        self.daily.reload()
        self.leave.reload()
        self.staff.reload()
        self.records.reload()
        lang = self.db.get_setting("language", "pt")
        if lang != i18n.language():
            self._language_changed(lang)

    def _retranslate_nav(self) -> None:
        for i, key in enumerate(NAV_KEYS):
            self.nav.item(i).setText(tr(key))

    def _language_changed(self, code: str) -> None:
        i18n.set_language(code)
        self._retranslate_nav()
        for page in (self.daily, self.staff, self.leave, self.records, self.settings, self.about):
            page.retranslate()

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if not self.daily.maybe_save():
            event.ignore()
            return
        self.statusBar().showMessage(tr("app.backup_closing"))
        QApplication.processEvents()
        # Automatic backup on every close; a failure only shows a warning.
        try:
            self.settings.run_backup(parent=self, quiet=True)
        except Exception:
            log.exception("automatic backup failed")
        event.accept()
