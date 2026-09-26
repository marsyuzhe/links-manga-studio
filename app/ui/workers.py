"""Short-lived jobs and replaceable bounded image queues."""
from __future__ import annotations
import logging
from collections import deque
from pathlib import Path
from threading import Condition, Event, Thread
from PySide6.QtCore import QObject, QThread, Signal
from app.cache.image_cache import ImageCache
from app.images.image_loader import ImageLoader
from app.images.thumbnail_service import ThumbnailService, image_key
from app.pdf.render import PdfRenderService, PREVIEW_DPI, THUMBNAIL_DPI
from app.database.database import connect
from app.rendering.renderer import PageRenderer


class Job(QThread):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, operation, parent=None) -> None:
        super().__init__(parent)
        self.operation = operation
        self.cancel = Event()

    def run(self) -> None:
        try:
            self.result.emit(self.operation(self.progress.emit, self.cancel))
        except Exception as exc:
            logging.exception("Background operation failed")
            self.error.emit(str(exc))


class ImageSignals(QObject):
    ready = Signal(int, str, object, str)


class ImageWorker:
    """One decoder; pending requests are replaced, never appended without bound."""
    def __init__(self, project: Path, cache: ImageCache, thumbnail: bool = False) -> None:
        self.signals = ImageSignals()
        self.project = project
        self.cache = cache
        self.thumbnail = thumbnail
        self.loader = ImageLoader()
        self.thumbnails = ThumbnailService(project) if thumbnail else None
        self.pdf = PdfRenderService(project)
        self._condition = Condition()
        self._queue: deque = deque()
        self._generation = 0
        self._stopped = False
        self.thread = Thread(target=self._run, daemon=True, name="LMW-thumbnail" if thumbnail else "LMW-image")
        self.thread.start()

    def request(self, generation: int, pages: list[dict]) -> None:
        with self._condition:
            self._generation = generation
            self._queue = deque(pages[:40 if self.thumbnail else 3])
            self._condition.notify()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._queue.clear()
            self._condition.notify()
        self.thread.join()

    @property
    def pending_count(self) -> int:
        with self._condition:
            return len(self._queue)

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._queue or self._stopped)
                if self._stopped:
                    return
                page = self._queue.popleft()
                generation = self._generation
            image, error = None, ""
            try:
                key = (f"pdf:{page['sha256']}:{page['source_page_index']}:"
                       f"{THUMBNAIL_DPI if self.thumbnail else PREVIEW_DPI}:{self.thumbnail}") if page.get("source_kind") == "pdf" else image_key(page)
                image = self.cache.get(key)
                if image is None:
                    if not self.thumbnail and page.get("has_render_edits"):
                        db = connect(self.project / "project.sqlite3")
                        try:
                            image = PageRenderer(db, self.project).render_page(page, PREVIEW_DPI, "preview")
                        finally:
                            db.close()
                    elif page.get("source_kind") == "pdf":
                        image = self.pdf.render(page, THUMBNAIL_DPI if self.thumbnail else PREVIEW_DPI,
                                                "thumbnail" if self.thumbnail else "preview")
                    else:
                        image = self.thumbnails.get(page) if self.thumbnail else self.loader.load(Path(page["path"]))
                    with self._condition:
                        if generation == self._generation and not self._stopped:
                            self.cache.put(key, image)
            except Exception as exc:
                error = "missing" if isinstance(exc, FileNotFoundError) else "broken"
                logging.exception("Image loading failed: %s", page["path"])
            with self._condition:
                if generation == self._generation and not self._stopped:
                    self.signals.ready.emit(generation, page["id"], image, error)
