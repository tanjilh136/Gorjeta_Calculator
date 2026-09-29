"""Generates the app logo:
  assets/app.ico   multi-size Windows icon (exe, desktop/Start menu shortcut, installer)
  assets/logo.png  512 px logo (loading screen, About page)

Run:  python tools/make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

TEAL_LIGHT = QColor("#2b9fae")
TEAL_DARK = QColor("#143f49")
MINT = QColor("#6fd0c4")
INK = QColor("#15505b")


def _font_family() -> str:
    fid = QFontDatabase.addApplicationFont(str(ASSETS / "fonts" / "DejaVuSans-Bold.ttf"))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    return fams[0] if fams else "Arial"


def render(size: int, family: str) -> QImage:
    s = float(size)
    small = size <= 24
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)

    # Rounded tile with a diagonal teal gradient.
    inset = s * (0.02 if small else 0.04)
    tile = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
    path = QPainterPath()
    path.addRoundedRect(tile, s * 0.22, s * 0.22)
    grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
    grad.setColorAt(0.0, TEAL_LIGHT)
    grad.setColorAt(1.0, TEAL_DARK)
    p.fillPath(path, grad)

    if not small:
        # Soft light from the top-left corner.
        glow = QRadialGradient(QPointF(s * 0.25, s * 0.18), s * 0.75)
        glow.setColorAt(0.0, QColor(255, 255, 255, 46))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, glow)

    # Coin.
    c = QPointF(s * 0.5, s * 0.5)
    r = s * (0.36 if small else 0.31)
    if not small:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(c + QPointF(0, s * 0.025), r, r)
    coin = QLinearGradient(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))
    coin.setColorAt(0.0, QColor("#ffffff"))
    coin.setColorAt(1.0, QColor("#dff3ef"))
    p.setPen(Qt.NoPen)
    p.setBrush(coin)
    p.drawEllipse(c, r, r)
    if size >= 32:
        ring = QPen(MINT, max(1.0, s * 0.022))
        p.setPen(ring)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, r * 0.83, r * 0.83)

    # Euro sign.
    font = QFont(family)
    font.setBold(True)
    font.setPixelSize(max(9, int(r * (1.3 if small else 1.12))))
    p.setFont(font)
    p.setPen(INK)
    p.drawText(QRectF(c.x() - r, c.y() - r - s * 0.01, 2 * r, 2 * r), Qt.AlignCenter, "€")

    if size >= 48:
        # Small sparkle: a tip on top.
        sp = QPointF(s * 0.77, s * 0.24)
        k = s * 0.065
        star = QPainterPath()
        star.moveTo(sp.x(), sp.y() - k)
        star.quadTo(sp.x(), sp.y(), sp.x() + k, sp.y())
        star.quadTo(sp.x(), sp.y(), sp.x(), sp.y() + k)
        star.quadTo(sp.x(), sp.y(), sp.x() - k, sp.y())
        star.quadTo(sp.x(), sp.y(), sp.x(), sp.y() - k)
        p.fillPath(star, MINT)
    p.end()
    return img


def _png(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def main() -> int:
    QGuiApplication(sys.argv)
    family = _font_family()

    pngs = [_png(render(sz, family)) for sz in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, data = b"", b""
    for size, png in zip(ICO_SIZES, pngs):
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    (ASSETS / "app.ico").write_bytes(header + entries + data)
    render(512, family).save(str(ASSETS / "logo.png"))
    print(f"wrote {ASSETS / 'app.ico'} and {ASSETS / 'logo.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
