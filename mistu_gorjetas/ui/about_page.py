"""About page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from .. import APP_NAME, VERSION, paths
from ..i18n import tr
from .widgets import page_title


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.title = page_title()

        self.logo_label = QLabel()
        logo = QPixmap(str(paths.resource_dir() / "logo.png"))
        if not logo.isNull():
            self.logo_label.setPixmap(logo.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.name_label = QLabel(APP_NAME)
        self.name_label.setObjectName("aboutName")
        self.version_label = QLabel()
        self.version_label.setObjectName("summary")
        self.desc_label = QLabel()
        self.credit_label = QLabel()
        self.credit_label.setObjectName("credit")
        self.data_label = QLabel()
        self.data_label.setObjectName("hint")
        self.data_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.data_label.setWordWrap(True)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(8)
        cl.addWidget(self.logo_label)
        cl.addSpacing(4)
        cl.addWidget(self.name_label)
        cl.addWidget(self.version_label)
        cl.addSpacing(6)
        cl.addWidget(self.desc_label)
        cl.addSpacing(14)
        cl.addWidget(self.credit_label)
        cl.addSpacing(14)
        cl.addWidget(self.data_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addWidget(card)
        layout.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(tr("about.title"))
        self.version_label.setText(tr("about.version", v=VERSION))
        self.desc_label.setText(tr("about.description"))
        self.credit_label.setText(tr("about.credit"))
        self.data_label.setText(f"{tr('about.data')} {paths.db_path()}")
