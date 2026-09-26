"""Generate original manga-like fixture pages and PDFs; no third-party artwork."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPdfWriter, QPageSize


def sample_page(path: Path, *, page_number: int = 1, vertical: bool = False) -> Path:
    """Draw a neutral panel, speech bubble and OCR-friendly Chinese/English text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(640, 900, QImage.Format.Format_RGB32)
    image.fill(QColor("#faf8f3"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#283343"), 3))
    painter.drawRect(25, 25, 590, 850)
    painter.drawLine(25, 460, 615, 460)
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(QRectF(100, 110, 440, 235))
    painter.setFont(QFont("Microsoft YaHei", 19))
    if vertical:
        for index, character in enumerate("竖排文字样本"):
            painter.drawText(310, 157 + index * 29, character)
    else:
        painter.drawText(QRectF(140, 160, 360, 60), Qt.AlignmentFlag.AlignCenter, "你好，世界！")
        painter.setFont(QFont("Arial", 17))
        painter.drawText(QRectF(140, 220, 360, 60), Qt.AlignmentFlag.AlignCenter, "HELLO WORLD")
    painter.setFont(QFont("Arial", 13))
    painter.drawText(42, 845, f"SYNTHETIC PAGE {page_number:03d}")
    painter.end()
    if not image.save(str(path)):
        raise OSError(f"Cannot save synthetic page: {path}")
    return path


def multi_page_pdf(path: Path, count: int = 3) -> Path:
    """Create original PDF panels using the existing Qt PDF writer."""
    if count < 1:
        raise ValueError("PDF must contain at least one page")
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(640, 900), QPageSize.Unit.Point))
    painter = QPainter(writer)
    try:
        for index in range(1, count + 1):
            if index > 1:
                writer.newPage()
            painter.setPen(QPen(QColor("#283343"), 2))
            painter.drawRect(QRectF(25, 25, 570, 810))
            painter.drawEllipse(QRectF(100, 100, 420, 230))
            painter.setFont(QFont("Arial", 21))
            painter.drawText(150, 220, f"HELLO WORLD {index:03d}")
            painter.setFont(QFont("Arial", 14))
            painter.drawText(45, 800, f"SYNTHETIC PAGE {index:03d}")
    finally:
        painter.end()
    return path
