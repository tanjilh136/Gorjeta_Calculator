"""Loading screen shown while the application starts."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QEventLoop,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from .. import APP_NAME, CREDIT, VERSION, paths

WIDTH, HEIGHT = 480, 320
MARGIN = 16  # room for the drop shadow
TEAL = QColor("#1f6f7f")
TEAL_DARK = QColor("#143f49")
MINT = QColor("#6fd0c4")


class SplashScreen(QWidget):
    """Logo, app name and credit, with an animated loading bar. Call finish()
    once the main window is ready; it fades out."""

    MIN_SECONDS = 1.8

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(WIDTH, HEIGHT)
        self._logo = QPixmap(str(paths.resource_dir() / "logo.png"))
        self._clock = QElapsedTimer()
        self._clock.start()
        self._started = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)
        self._fade = None
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - WIDTH // 2, geo.center().y() - HEIGHT // 2)

    # ---------------------------------------------------------------- api
    def pump(self) -> None:
        """Keep the animation running between loading steps."""
        QApplication.processEvents()

    def wait_minimum(self) -> None:
        """Stay visible for at least MIN_SECONDS so it doesn't just flash."""
        remaining = self.MIN_SECONDS - (time.monotonic() - self._started)
        if remaining > 0:
            loop = QEventLoop()
            QTimer.singleShot(int(remaining * 1000), loop.quit)
            loop.exec()

    def finish(self) -> None:
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(280)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.InQuad)
        self._fade.finished.connect(self.close)
        self._fade.start()

    # ------------------------------------------------------------- drawing
    def paintEvent(self, _event) -> None:
        t = self._clock.elapsed() / 1000.0
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.TextAntialiasing)

        card = QRectF(MARGIN, MARGIN, WIDTH - 2 * MARGIN, HEIGHT - 2 * MARGIN)

        # Soft shadow.
        for i in range(MARGIN, 0, -2):
            shadow = QPainterPath()
            shadow.addRoundedRect(card.adjusted(-i, -i + 4, i, i + 4), 18 + i, 18 + i)
            p.fillPath(shadow, QColor(0, 0, 0, int(5 * (1 - i / MARGIN)) + 1))

        path = QPainterPath()
        path.addRoundedRect(card, 18, 18)
        bg = QLinearGradient(card.topLeft(), card.bottomRight())
        bg.setColorAt(0.0, QColor("#ffffff"))
        bg.setColorAt(1.0, QColor("#eef6f6"))
        p.fillPath(path, bg)

        # Top accent band.
        p.save()
        p.setClipPath(path)
        band = QLinearGradient(card.topLeft(), card.topRight())
        band.setColorAt(0.0, TEAL)
        band.setColorAt(1.0, MINT)
        p.fillRect(QRectF(card.left(), card.top(), card.width(), 5), band)
        p.restore()

        # Logo: eases in (scale + fade) during the first 0.5 s, then breathes gently.
        intro = min(1.0, t / 0.5)
        ease = 1 - (1 - intro) ** 3
        breathe = 1 + 0.025 * math.sin(t * 2.4) if intro >= 1 else 1
        size = 96 * (0.85 + 0.15 * ease) * breathe
        centre = QPointF(WIDTH / 2, card.top() + 84)
        if not self._logo.isNull():
            p.setOpacity(ease)
            p.drawPixmap(
                QRectF(centre.x() - size / 2, centre.y() - size / 2, size, size),
                self._logo, QRectF(self._logo.rect()),
            )
            p.setOpacity(1.0)

        # Texts fade in slightly after the logo.
        text_alpha = max(0.0, min(1.0, (t - 0.2) / 0.4))
        p.setOpacity(text_alpha)
        title = QFont("Segoe UI", 22)
        title.setBold(True)
        p.setFont(title)
        p.setPen(QColor("#17545f"))
        p.drawText(QRectF(card.left(), card.top() + 140, card.width(), 40), Qt.AlignCenter, APP_NAME)

        credit = QFont("Segoe UI", 10)
        p.setFont(credit)
        p.setPen(QColor("#5f6f74"))
        p.drawText(QRectF(card.left(), card.top() + 178, card.width(), 22), Qt.AlignCenter, CREDIT)

        # Indeterminate loading bar: a pill sliding across a track.
        track = QRectF(WIDTH / 2 - 110, card.top() + 222, 220, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#d9e6e8"))
        p.drawRoundedRect(track, 3, 3)
        phase = (t * 0.75) % 1.0
        pos = (1 - math.cos(phase * math.pi)) / 2  # ease in-out
        pill_w = 70
        x = track.left() - pill_w + pos * (track.width() + pill_w)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(track, 3, 3)
        p.setClipPath(clip)
        pill = QLinearGradient(QPointF(x, 0), QPointF(x + pill_w, 0))
        pill.setColorAt(0.0, TEAL)
        pill.setColorAt(1.0, MINT)
        p.setBrush(pill)
        p.drawRoundedRect(QRectF(x, track.top(), pill_w, track.height()), 3, 3)
        p.restore()

        small = QFont("Segoe UI", 8)
        p.setFont(small)
        p.setPen(QColor("#9aa7ab"))
        p.drawText(QRectF(card.left(), card.bottom() - 30, card.width(), 18), Qt.AlignCenter, f"v{VERSION}")
        p.setOpacity(1.0)
        p.end()
