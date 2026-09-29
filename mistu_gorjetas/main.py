"""Application entry point."""

from __future__ import annotations

import logging
import sys
import traceback
from datetime import date
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, VERSION, i18n, licensing, paths
from .db import Database, retention_cutoff
from .i18n import tr

log = logging.getLogger("mistu_gorjetas")

# Name checked by the installer (AppMutex) so it can ask to close the app first.
APP_MUTEX = "MistuGorjetasAppMutex"


def _setup_logging() -> None:
    handler = RotatingFileHandler(paths.log_path(), maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb):
        log.error("unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            from .ui.widgets import error

            error(None, tr("app.unexpected", error=exc, log=paths.log_path()))
        except Exception:
            pass

    sys.excepthook = hook


class _SingleInstance:
    """Windows: named mutex (also used by the installer's AppMutex check); the OS
    releases it when the process ends, even after a crash or power cut.
    Elsewhere: a lock file whose stale owner is detected by PID."""

    def __init__(self):
        self._handle = None
        self._lock = None

    def acquire(self) -> bool:
        if sys.platform == "win32":
            import ctypes

            ERROR_ALREADY_EXISTS = 183
            kernel32 = ctypes.windll.kernel32
            self._handle = kernel32.CreateMutexW(None, False, APP_MUTEX)
            return bool(self._handle) and kernel32.GetLastError() != ERROR_ALREADY_EXISTS
        self._lock = QLockFile(str(paths.user_data_dir() / "app.lock"))
        self._lock.setStaleLockTime(2_000_000_000)  # only a dead owner makes it stale
        return self._lock.tryLock(100)

    def release(self) -> None:
        if self._lock is not None:
            self._lock.unlock()


def _app_icon() -> QIcon:
    ico = paths.resource_dir() / "app.ico"
    return QIcon(str(ico)) if ico.exists() else QIcon()


def _check_license(app: QApplication) -> bool:
    from .ui.activation_dialog import ActivationDialog
    from .ui.widgets import error

    if not licensing.is_configured():
        if paths.is_frozen():
            error(None, tr("act.not_configured"))
            return False
        log.warning("no install key configured - licensing skipped (development run)")
        return True

    status = licensing.check_activation()
    if status == licensing.Status.OK:
        return True
    log.info("activation required: %s", status.value)
    dlg = ActivationDialog(moved=status == licensing.Status.WRONG_MACHINE)
    dlg.setWindowIcon(app.windowIcon())
    return dlg.exec() == ActivationDialog.Accepted


def main() -> int:
    _setup_logging()
    log.info("%s %s starting", APP_NAME, VERSION)
    _install_excepthook()

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Optivex Labs")
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(_app_icon())
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"OptivexLabs.{APP_ID}")
        except Exception:
            pass

    from .ui.splash import SplashScreen
    from .ui.style import apply_style
    from .ui.widgets import info

    apply_style(app)

    instance = _SingleInstance()
    if not instance.acquire():
        info(None, tr("app.already_running"), title=APP_NAME)
        return 0

    splash = SplashScreen()
    splash.show()
    splash.pump()

    from .ui.main_window import MainWindow  # the heavy imports happen behind the splash

    splash.pump()
    db = Database(paths.db_path())
    i18n.set_language(db.get_setting("language", "pt"))
    splash.pump()

    if licensing.is_configured() and licensing.check_activation() != licensing.Status.OK:
        splash.hide()  # the activation dialog takes over
    if not _check_license(app):
        splash.close()
        return 1

    removed = db.purge_older_than(retention_cutoff(date.today()))
    if removed:
        log.info("retention: removed %d day(s) older than 5 years", removed)

    window = MainWindow(db)
    splash.pump()
    if splash.isVisible():
        splash.wait_minimum()
    window.show()
    if splash.isVisible():
        splash.raise_()
        splash.finish()
    else:
        splash.close()
    code = app.exec()
    db.close()
    instance.release()
    return code


if __name__ == "__main__":
    sys.exit(main())
