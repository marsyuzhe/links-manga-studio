"""Thread-safe, byte-budgeted LRU for QImage objects."""
from collections import OrderedDict
from threading import RLock
from PySide6.QtGui import QImage


class ImageCache:
    """Own decoded QImages within a byte budget; UI pixmaps and disk caches have separate owners."""
    def __init__(self, limit_bytes: int = 512 * 1024 * 1024) -> None:
        self.limit_bytes = max(0, limit_bytes)
        self.used_bytes = 0
        self.evictions = 0
        self._items: OrderedDict[str, QImage] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> QImage | None:
        with self._lock:
            image = self._items.get(key)
            if image is not None:
                self._items.move_to_end(key)
            return image

    def put(self, key: str, image: QImage) -> None:
        with self._lock:
            previous = self._items.pop(key, None)
            if previous is not None:
                self.used_bytes -= previous.sizeInBytes()
            size = image.sizeInBytes()
            if size > self.limit_bytes:
                # A single oversized page must not evict every useful cached preview.
                return
            while self._items and self.used_bytes + size > self.limit_bytes:
                _, old = self._items.popitem(last=False)
                self.used_bytes -= old.sizeInBytes()
                self.evictions += 1
            self._items[key] = image
            self.used_bytes += size

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.used_bytes = 0

    @property
    def keys(self) -> list[str]:
        with self._lock:
            return list(self._items)
