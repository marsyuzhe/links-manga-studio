"""Immediate transactional non-destructive rendering edits."""
from __future__ import annotations

import json
import sqlite3
import uuid
import shutil
from app.history import HistoryService
from pathlib import Path


class RenderEditService:
    def __init__(self, connection: sqlite3.Connection, project: Path) -> None:
        self.db = connection
        self.project = project

    def set_erase(self, block_id: str, mode: str, color: str = "#ffffff", radius: int = 3) -> None:
        if mode not in ("none", "fill", "telea", "ns"):
            raise ValueError("Unknown erase mode")
        if not 1 <= radius <= 50:
            raise ValueError("Invalid inpaint radius")
        config = {} if mode == "none" else {"mode": mode, "color": color, "radius": radius}
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        with self.db:
            self.db.execute("UPDATE text_blocks SET erase_data_json=?,erase_status=?,revision=revision+1 WHERE id=?",
                            (json.dumps(config), "none" if mode == "none" else "erased", block_id))
            history.record("text_blocks", block_id, before, "erase")

    def set_style(self, block_id: str, settings: dict) -> str:
        block = self.db.execute("SELECT page_id,style_id FROM text_blocks WHERE id=?", (block_id,)).fetchone()
        if block is None:
            raise ValueError("Unknown text block")
        project_id = self.db.execute("SELECT project_id FROM pages WHERE id=?", (block["page_id"],)).fetchone()[0]
        style_id = block["style_id"] or str(uuid.uuid4())
        history = HistoryService(self.db)
        style_before = history.snapshot("styles", style_id)
        block_before = history.snapshot("text_blocks", block_id)
        with self.db:
            if block["style_id"]:
                self.db.execute("UPDATE styles SET settings_json=?,revision=revision+1 WHERE id=?",
                                (json.dumps(settings, ensure_ascii=False), style_id))
            else:
                self.db.execute("INSERT INTO styles(id,project_id,name,settings_json) VALUES(?,?,?,?)",
                                (style_id, project_id, "Text style", json.dumps(settings, ensure_ascii=False)))
                self.db.execute("UPDATE text_blocks SET style_id=?,revision=revision+1 WHERE id=?", (style_id, block_id))
            self.db.execute("UPDATE text_blocks SET text_style=? WHERE id=?",
                            (json.dumps(settings, ensure_ascii=False), block_id))
            history.record("styles", style_id, style_before, "style")
            history.record("text_blocks", block_id, block_before, "style_link")
        return style_id

    def set_mask(self, block_id: str, image) -> Path:
        from PySide6.QtGui import QImage
        if not isinstance(image, QImage) or image.isNull():
            raise ValueError("Mask image is empty")
        target = self.project / "masks" / f"{block_id}.png"
        target.parent.mkdir(exist_ok=True)
        versions = target.parent / ".history"
        versions.mkdir(exist_ok=True)
        before_file = versions / f"{uuid.uuid4().hex}.png" if target.exists() else None
        if before_file:
            shutil.copy2(target, before_file)
        temporary = target.with_name(f"{uuid.uuid4().hex[:12]}.png")
        try:
            if not image.save(str(temporary), "PNG"):
                raise OSError("Cannot save mask")
            temporary.replace(target)
            after_file = versions / f"{uuid.uuid4().hex}.png"
            shutil.copy2(target, after_file)
            history = HistoryService(self.db)
            before_row = history.snapshot("text_blocks", block_id)
            with self.db:
                history.record_mask(block_id, target, before_file, after_file)
                self.db.execute("UPDATE text_blocks SET mask_path=?,revision=revision+1 WHERE id=?",
                                (str(target.relative_to(self.project)), block_id))
                history.record("text_blocks", block_id, before_row, "mask_link")
            return target
        finally:
            temporary.unlink(missing_ok=True)
