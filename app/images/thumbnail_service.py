"""Versioned on-disk thumbnails, generated outside the UI thread."""
import hashlib
import os
import uuid
from pathlib import Path
from PySide6.QtGui import QImage
from .image_loader import ImageLoader


def image_key(page: dict) -> str:
    path = Path(page["path"])
    stat = path.stat()
    return f"{page['source_file_id']}:{stat.st_size}:{stat.st_mtime_ns}:{path}"


class ThumbnailService:
    VERSION = 1

    def __init__(self, project: Path) -> None:
        self.root = project / "cache" / "thumbnails"
        self.root.mkdir(parents=True, exist_ok=True)
        self.loader = ImageLoader()

    def path_for(self, page: dict) -> Path:
        digest = hashlib.sha256(image_key(page).encode("utf-8")).hexdigest()[:24]
        return self.root / f"v{self.VERSION}_{digest}.png"

    def get(self, page: dict) -> QImage:
        target = self.path_for(page)  # checks source presence before serving cache
        if target.exists():
            image = QImage(str(target))
            if not image.isNull():
                return image
        image = self.loader.load(Path(page["path"]), 256)
        temp = target.with_name(target.name + f".{uuid.uuid4()}.tmp")
        try:
            if not image.save(str(temp), "PNG"):
                raise OSError(f"Cannot write thumbnail: {target}")
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return image
