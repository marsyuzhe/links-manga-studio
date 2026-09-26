from PySide6.QtGui import QImage
from app.cache.image_cache import ImageCache


def test_byte_budget_lru_and_oversize():
    image = QImage(100, 100, QImage.Format.Format_RGB32)
    size = image.sizeInBytes()
    cache = ImageCache(size*2)
    cache.put("a", image)
    cache.put("b", image)
    cache.get("a")
    cache.put("c", image)
    assert cache.keys == ["a", "c"]
    assert cache.used_bytes <= cache.limit_bytes and cache.evictions == 1
    cache.put("huge", QImage(1000, 1000, QImage.Format.Format_RGB32))
    assert "huge" not in cache.keys
    cache.clear()
    assert cache.used_bytes == 0
