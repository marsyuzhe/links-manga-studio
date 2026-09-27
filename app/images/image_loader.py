"""Unicode-safe decoding with a single, EXIF-normalized coordinate space."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader

MAX_PIXELS = 64_000_000
QImageReader.setAllocationLimit(256)


class ImageLoadError(RuntimeError):
    """A missing, corrupt or unsupported image."""


class ImageLoader:
    """Return QImage (safe off the UI thread), never QPixmap."""

    @staticmethod
    def reader(path: Path) -> QImageReader:
        if not path.is_file():
            raise FileNotFoundError(f"Missing Source: {path}")
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
            raise ImageLoadError(f"Invalid image or image exceeds 64 megapixels: {path.name}")
        return reader

    def load(self, path: Path, max_side: int | None = None) -> QImage:
        reader = self.reader(path)
        if max_side:
            reader.setScaledSize(reader.size().scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            raise ImageLoadError(f"Broken Image: {path.name}: {reader.errorString()}")
        if max_side:
            image = image.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        return image

    def metadata(self, path: Path) -> dict:
        reader = self.reader(path)
        fmt = bytes(reader.format()).decode("ascii", errors="replace")
        orientation = reader.transformation().value
        image = reader.read()  # Sequential full decode validates each file; never retained.
        if image.isNull():
            raise ImageLoadError(f"Broken Image: {path.name}: {reader.errorString()}")
        return {"width": image.width(), "height": image.height(), "format": fmt,
                "orientation": orientation, "orientation_policy": "qt-auto-transform-v1",
                "color_mode": image.format().name, "dpi_x": image.dotsPerMeterX() * .0254,
                "dpi_y": image.dotsPerMeterY() * .0254}
