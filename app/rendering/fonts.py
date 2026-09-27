"""Cached Windows font-family index for typesetting search and preview."""
from __future__ import annotations

import json
import time
from pathlib import Path


class FontCatalog:
    """Cache installed font metadata; callers request scanning only for font/quality tools."""
    def __init__(self, cache_path: Path, fonts_dir: Path = Path("C:/Windows/Fonts")) -> None:
        self.cache_path = cache_path
        self.fonts_dir = fonts_dir

    def load(self) -> list[str]:
        files = sorted((path for path in self.fonts_dir.iterdir() if path.suffix.lower() in
                       (".ttf", ".otf", ".ttc")), key=lambda path: path.name.casefold())
        fingerprint = [(path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in files]
        if self.cache_path.exists():
            try:
                cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if cached["fingerprint"] == [list(item) for item in fingerprint]:
                    return cached["families"]
            except (ValueError, KeyError, OSError):
                pass
        from fontTools.ttLib import TTCollection, TTFont
        families: set[str] = set()
        for path in files:
            try:
                if path.suffix.lower() == ".ttc":
                    collection = TTCollection(path, lazy=True)
                    fonts = collection.fonts
                else:
                    collection = None
                    fonts = [TTFont(path, lazy=True)]
                try:
                    for font in fonts:
                        for record in font["name"].names:
                            if record.nameID == 1:
                                families.add(record.toUnicode())
                finally:
                    for font in fonts:
                        font.close()
                    if collection is not None:
                        collection.close()
            except Exception:
                continue
        result = sorted(families, key=str.casefold)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps({"fingerprint": fingerprint, "families": result}, ensure_ascii=False),
                                   encoding="utf-8")
        return result

    def metadata(self) -> list[dict]:
        """Cache file metadata and CJK coverage; call from a worker, not the UI thread."""
        paths = sorted((p for p in self.fonts_dir.iterdir() if p.suffix.lower() in
                        (".ttf", ".otf", ".ttc")), key=lambda p: p.name.casefold())
        fingerprint = [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in paths]
        # Cheap file metadata validates the cache before opening font tables or checking glyph coverage.
        path = self.cache_path.with_name("font_metadata.json")
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached["fingerprint"] == fingerprint:
                return cached["fonts"]
        except (FileNotFoundError, ValueError, KeyError, OSError):
            pass
        from fontTools.ttLib import TTCollection, TTFont
        records: dict[str, dict] = {}
        for font_path in paths:
            collection = None
            fonts = []
            try:
                if font_path.suffix.lower() == ".ttc":
                    collection = TTCollection(font_path, lazy=True)
                    fonts = collection.fonts
                else:
                    fonts = [TTFont(font_path, lazy=True)]
                for font in fonts:
                    names = font["name"].names
                    family = next((r.toUnicode() for r in names if r.nameID == 1), None)
                    if not family:
                        continue
                    lower = family.casefold()
                    category = ("serif" if any(v in lower for v in ("serif", "song", "mincho", "宋", "明朝")) else
                                "handwritten" if any(v in lower for v in ("hand", "script", "brush", "楷")) else
                                "rounded" if any(v in lower for v in ("rounded", "round", "圆")) else
                                "display" if any(v in lower for v in ("display", "impact", "黑体")) else "sans")
                    cmap = font.getBestCmap() or {}
                    weight = int(font["OS/2"].usWeightClass) if "OS/2" in font else 400
                    italic = bool(font["head"].macStyle & 2) if "head" in font else False
                    record = {"family": family, "style": "Italic" if italic else "Regular",
                              "weight": weight, "italic": italic, "file_path": str(font_path),
                              "supported_languages": ["zh"] if all(ord(c) in cmap for c in "中文") else [],
                              "category": category, "last_seen": int(time.time())}
                    old = records.get(family)
                    if old is None or (record["supported_languages"] and not old["supported_languages"]):
                        records[family] = record
            except Exception:
                continue
            finally:
                for font in fonts:
                    font.close()
                if collection:
                    collection.close()
        result = sorted(records.values(), key=lambda row: row["family"].casefold())
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"fingerprint": fingerprint, "fonts": result}, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
        return result

    def search(self, query: str) -> list[dict]:
        query = query.casefold().strip()
        return [row for row in self.metadata() if query in row["family"].casefold()]

    def missing(self, family: str) -> bool:
        return family.casefold() not in {row["family"].casefold() for row in self.metadata()}

    def supports_chinese(self, family: str) -> bool:
        return any(row["family"].casefold() == family.casefold() and
                   "zh" in row["supported_languages"] for row in self.metadata())

    def fallback(self, family: str, text: str) -> str:
        if not self.missing(family) and (not any('\u4e00' <= c <= '\u9fff' for c in text)
                                          or self.supports_chinese(family)):
            return family
        for candidate in ("Microsoft YaHei", "SimHei", "SimSun"):
            if not self.missing(candidate) and self.supports_chinese(candidate):
                return candidate
        return next((r["family"] for r in self.metadata() if "zh" in r["supported_languages"]), family)


class FontPreferences:
    def __init__(self, config):
        self.config = config

    @property
    def favorites(self) -> list[str]:
        return list(self.config.data.get("favorite_fonts", []))

    @property
    def recent(self) -> list[str]:
        return list(self.config.data.get("recent_fonts", []))

    def toggle_favorite(self, family: str) -> None:
        names = self.favorites
        if family in names:
            names.remove(family)
        else:
            names.insert(0, family)
        self.config.data["favorite_fonts"] = names[:100]
        self.config.save()

    def used(self, family: str) -> None:
        self.config.data["recent_fonts"] = [family] + [x for x in self.recent if x != family][:19]
        self.config.save()
