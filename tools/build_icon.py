"""Generate the original geometric application icon and its multi-size ICO."""
from pathlib import Path
import struct
from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1] / "assets" / "icons"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 256, size / 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#182837"))
    painter.drawRoundedRect(QRectF(2, 2, 252, 252), 42, 42)
    page = QPainterPath()
    page.moveTo(55, 35)
    page.lineTo(162, 35)
    page.lineTo(207, 80)
    page.lineTo(207, 218)
    page.lineTo(55, 218)
    page.closeSubpath()
    painter.setBrush(QColor("#f5f6ed"))
    painter.drawPath(page)
    painter.setBrush(QColor("#26c4c4"))
    painter.drawPolygon([QPointF(x, y) for x, y in ((162, 35), (162, 80), (207, 80))])
    pen = QPen(QColor("#182837"), 24, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(92, 106, 92, 179)
    painter.drawLine(92, 179, 153, 179)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#26c4c4"))
    painter.drawRoundedRect(QRectF(155, 135, 32, 32), 11, 11)
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    blobs = []
    for size in SIZES:
        image = draw(size)
        assert image.save(str(ROOT / f"app_icon_{size}.png"), "PNG")
        blobs.append(png_bytes(image))
    assert draw(256).save(str(ROOT / "app_icon.png"), "PNG")
    header = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    directory = bytearray()
    for size, data in zip(SIZES, blobs):
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (ROOT / "app_icon.ico").write_bytes(header + directory + b"".join(blobs))


if __name__ == "__main__":
    main()
