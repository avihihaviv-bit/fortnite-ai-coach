"""Generate src/fortnite_coach/assets/app.ico (and app.png) with Qt only.

The icon is the app's own crosshair glyph on a purple-to-green rounded square.
ICO entries are stored as PNG (supported by Windows Vista and later).
Run: python packaging/make_icon.py
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = Path(__file__).resolve().parents[1] / "src" / "fortnite_coach" / "assets"


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    grad = QLinearGradient(QPointF(0, 0), QPointF(s, s))
    grad.setColorAt(0, QColor("#8B5CF6"))
    grad.setColorAt(1, QColor("#22C55E"))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(max(1.5, s * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    c, r = s / 2, s * 0.25
    p.drawEllipse(QPointF(c, c), r, r)
    for a, b in (((c, s * 0.14), (c, s * 0.34)), ((c, s * 0.66), (c, s * 0.86)),
                 ((s * 0.14, c), (s * 0.34, c)), ((s * 0.66, c), (s * 0.86, c))):
        p.drawLine(QPointF(*a), QPointF(*b))
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QPointF(c, c), s * 0.04, s * 0.04)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    images = [(sz, png_bytes(render(sz))) for sz in SIZES]
    (OUT / "app.ico").write_bytes(build_ico(images))
    (OUT / "app.png").write_bytes(images[-1][1])
    print(f"wrote {OUT / 'app.ico'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
