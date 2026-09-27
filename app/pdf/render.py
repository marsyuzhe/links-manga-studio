"""PDF raster cache and conversions in a stable 72-dpi page coordinate space."""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pypdfium2 as pdfium
from PySide6.QtGui import QImage


RENDER_VERSION = 2
PREVIEW_DPI = 110
THUMBNAIL_DPI = 24
MAX_RENDER_PIXELS = 64_000_000


def page_to_render(value: float, page_extent: float, render_extent: int) -> float:
    return value * render_extent / page_extent


def render_to_page(value: float, page_extent: float, render_extent: int) -> float:
    return value * page_extent / render_extent


class PdfRenderService:
    """Render requested PDF pages only; source page indices and page coordinates stay unchanged."""
    def __init__(self, project: Path) -> None:
        self.root = project / "cache" / "pdf_render"

    def cache_path(self, page: dict, dpi: int, purpose: str) -> Path:
        if purpose not in ("preview", "ocr", "thumbnail") or dpi < 12 or dpi > 600:
            raise ValueError("Unsupported PDF render purpose or DPI")
        key = f"{page['sha256']}:{page['source_page_index']}:{dpi}:{RENDER_VERSION}"
        name = hashlib.sha256(key.encode("ascii")).hexdigest()[:24]
        return self.root / purpose / f"{name}.png"

    def render(self, page: dict, dpi: int = PREVIEW_DPI, purpose: str = "preview") -> QImage:
        source = Path(page["path"])
        if not source.is_file():
            raise FileNotFoundError(f"Missing Source: {source}")
        target = self.cache_path(page, dpi, purpose)
        if target.exists():
            cached = QImage(str(target))
            if not cached.isNull():
                return cached
        document = pdfium.PdfDocument(source)
        try:
            pdf_page = document[page["source_page_index"]]
            width, height = pdf_page.get_size()
            width = round(width * dpi / 72)
            height = round(height * dpi / 72)
            if width * height > MAX_RENDER_PIXELS:
                raise ValueError("PDF render exceeds 64 megapixels; use a lower DPI")
            bitmap = pdf_page.render(scale=dpi / 72)
            pil_image = bitmap.to_pil().convert("RGB")
            image = QImage(pil_image.tobytes(), pil_image.width, pil_image.height,
                           pil_image.width * 3, QImage.Format.Format_RGB888).copy()
            pdf_page.close()
        finally:
            document.close()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{uuid.uuid4().hex[:12]}.tmp")
        try:
            if not image.save(str(temporary), "PNG"):
                raise OSError(f"Cannot save PDF render: {target}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return image
