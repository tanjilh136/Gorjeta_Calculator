"""Application look: Fusion style, fixed light palette, style sheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

ACCENT = "#1f6f7f"
ACCENT_DARK = "#17545f"
SIDEBAR = "#17323a"

QSS = f"""
QWidget {{ font-size: 10pt; color: #1b1f21; }}
QMainWindow, #content {{ background: #f4f6f7; }}

#sidebar {{ background: {SIDEBAR}; }}
#sidebarTitle {{ color: white; font-size: 15pt; font-weight: 700; padding: 22px 18px 2px 18px; }}
#sidebarSub {{ color: #8fb3bb; font-size: 9pt; padding: 0 18px 18px 18px; }}
#sidebarCredit {{ color: #7d9aa1; font-size: 8pt; padding: 12px 18px 16px 18px; }}
#nav {{ background: transparent; border: none; outline: none; }}
#nav::item {{ color: #d5e3e6; padding: 11px 18px; border-left: 4px solid transparent; }}
#nav::item:hover {{ background: #1f424b; }}
#nav::item:selected {{ background: #245561; color: white; border-left: 4px solid #6fd0c4; }}

#pageTitle {{ font-size: 17pt; font-weight: 700; color: {ACCENT_DARK}; }}
#hint {{ color: #6b777c; font-size: 9pt; }}
#summary {{ color: #3d4a4f; }}
#summaryStrong {{ font-weight: 700; font-size: 11pt; }}
#weekday {{ font-size: 12pt; font-weight: 600; color: #3d4a4f; }}
#credit {{ color: {ACCENT_DARK}; font-weight: 600; }}
#aboutName {{ font-size: 20pt; font-weight: 700; color: {ACCENT_DARK}; }}
#errorText {{ color: #b03a2e; font-weight: 600; }}

#card, QGroupBox {{
    background: white; border: 1px solid #dde4e6; border-radius: 8px;
}}
QGroupBox {{ margin-top: 14px; padding: 16px 12px 12px 12px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {ACCENT_DARK}; }}
QGroupBox QLabel, #card QLabel {{ font-weight: normal; }}
#card QLabel#summaryStrong {{ font-weight: 700; }}
#card QLabel#aboutName {{ font-weight: 700; }}
#card QLabel#credit {{ font-weight: 600; }}

#status {{ padding: 6px 12px; border-radius: 12px; font-weight: 600; }}
#status[state="saved"] {{ background: #e3f3e8; color: #1e7a3c; }}
#status[state="unsaved"] {{ background: #fdf0d9; color: #a15c00; }}
#status[state="new"] {{ background: #e9eef0; color: #56646a; }}

QPushButton {{
    background: white; border: 1px solid #c5d0d3; border-radius: 6px; padding: 7px 14px;
}}
QPushButton:hover {{ background: #eef4f5; border-color: {ACCENT}; }}
QPushButton:pressed {{ background: #e0eaec; }}
QPushButton:disabled {{ color: #a7b1b4; background: #f3f5f6; border-color: #dfe5e7; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#primary:disabled {{ background: #a9c4c9; border-color: #a9c4c9; }}
QPushButton#danger {{ color: #b03a2e; border-color: #e0b4ae; }}
QPushButton#danger:hover {{ background: #fbeceb; }}
QPushButton#iconButton {{ padding: 6px 10px; min-width: 18px; }}

QLineEdit, QDateEdit, QComboBox, QDoubleSpinBox {{
    background: white; border: 1px solid #c5d0d3; border-radius: 5px; padding: 5px 7px;
}}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit#amount {{ font-size: 13pt; font-weight: 600; padding: 6px 9px; }}
QLineEdit[invalid="true"] {{ border: 2px solid #c0392b; background: #fdf1f0; }}
QCalendarWidget QAbstractItemView:disabled {{ color: #c3c9cc; }}
QDateEdit#readonlyDate {{ background: #eef2f3; color: #3d4a4f; }}
QDateEdit#bigDate {{ font-size: 12pt; font-weight: 600; min-width: 140px; }}

QTableWidget, QTreeWidget {{
    background: white; alternate-background-color: #f6f9f9; border: 1px solid #dde4e6;
    border-radius: 6px; selection-background-color: #d3e8ec; selection-color: #1b1f21;
}}
QTableWidget::item, QTreeWidget::item {{ padding: 5px 6px; }}
QHeaderView::section {{
    background: #eaf0f1; color: #3d4a4f; font-weight: 600; border: none;
    border-bottom: 1px solid #d3dcde; padding: 6px;
}}
"""


def apply_style(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#f4f6f7"))
    pal.setColor(QPalette.WindowText, QColor("#1b1f21"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f6f9f9"))
    pal.setColor(QPalette.Text, QColor("#1b1f21"))
    pal.setColor(QPalette.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ButtonText, QColor("#1b1f21"))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipText, QColor("#1b1f21"))
    pal.setColor(QPalette.PlaceholderText, QColor("#9aa4a8"))
    app.setPalette(pal)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(QSS)
