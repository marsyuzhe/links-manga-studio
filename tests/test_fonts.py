import shutil
from pathlib import Path

from app.rendering.fonts import FontCatalog


def test_font_catalog_cache_and_invalidation(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    shutil.copy2(Path("C:/Windows/Fonts/arial.ttf"), fonts / "arial.ttf")
    catalog = FontCatalog(tmp_path / "cache.json", fonts)
    first = catalog.load()
    assert any("Arial" in name for name in first)
    assert catalog.load() == first
    assert catalog.cache_path.is_file()
    (fonts / "arial.ttf").touch()
    assert catalog.load() == first
