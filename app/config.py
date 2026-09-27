"""Small, atomic user configuration store."""
from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    # COMPATIBILITY: keep the legacy directory name so existing user preferences survive rebranding.
    root = Path(os.environ.get("LMW_CONFIG_DIR", Path(os.environ.get("APPDATA", Path.home())) / "LinksMangaWorkspace"))
    root.mkdir(parents=True, exist_ok=True)
    return root


class Config:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_dir() / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.data = {}
        except (ValueError, OSError):
            self.data = {}

    @property
    def image_cache_mb(self) -> int:
        try:
            return max(16, min(2048, int(self.data.get("image_cache_mb", 512))))
        except (TypeError, ValueError):
            return 512

    @property
    def recent_projects(self) -> list[str]:
        return [p for p in self.data.get("recent_projects", []) if isinstance(p, str)]

    def add_recent(self, path: Path) -> None:
        value = str(path.resolve())
        self.data["recent_projects"] = [value] + [p for p in self.recent_projects if p != value][:9]
        self.save()

    def save(self) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
