"""Asks for the install key and binds the installation to this machine."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import APP_NAME, CREDIT, licensing
from ..i18n import tr

log = logging.getLogger(__name__)


class ActivationDialog(QDialog):
    def __init__(self, moved: bool):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} – {tr('act.title')}")
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        heading = QLabel(tr("act.heading"))
        heading.setObjectName("pageTitle")
        text = QLabel(tr("act.text_moved") if moved else tr("act.text_new"))
        text.setWordWrap(True)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setMinimumHeight(34)
        self.show_box = QCheckBox(tr("act.show"))
        self.show_box.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel(tr("act.key")))
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.show_box)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorText")
        self.error_label.setWordWrap(True)

        quit_btn = QPushButton(tr("act.quit"))
        quit_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(tr("act.activate"))
        self.ok_btn.setObjectName("primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._activate)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(quit_btn)
        buttons.addWidget(self.ok_btn)

        credit = QLabel(CREDIT)
        credit.setObjectName("hint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addLayout(key_row)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        layout.addWidget(credit)

    def _activate(self) -> None:
        self.ok_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = licensing.activate(self.key_edit.text())
        except OSError as exc:
            log.exception("activation could not be written")
            self.error_label.setText(tr("act.write_fail", error=exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.ok_btn.setEnabled(True)
        if ok:
            self.accept()
        else:
            self.error_label.setText(tr("act.wrong"))
            self.key_edit.selectAll()
            self.key_edit.setFocus()
