"""Transactional OCR review and manual translation edits."""
from __future__ import annotations

import sqlite3
import uuid
import json
from app.history import HistoryService
from datetime import datetime, timezone


class TextBlockService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def for_page(self, page_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM text_blocks WHERE page_id=? AND active=1 ORDER BY reading_order,sequence", (page_id,))]

    def update_review(self, block_id: str, source_text: str, reading_order: int,
                      region_type: str = "speech") -> None:
        if reading_order < 1:
            raise ValueError("Reading order must be positive")
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        with self.db:
            changed = self.db.execute("""UPDATE text_blocks SET source_text=?,reading_order=?,region_type=?,
                review_status='reviewed',revision=revision+1 WHERE id=? AND active=1""",
                (source_text, reading_order, region_type, block_id)).rowcount
            if not changed:
                raise ValueError("Text block no longer exists")
            history.record("text_blocks", block_id, before, "ocr_review")

    def update_geometry(self, block_id: str, bbox: list[float], rotation: float = 0) -> None:
        if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1] or not -360 <= rotation <= 360:
            raise ValueError("Invalid text block geometry")
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        if before is None:
            raise ValueError("Unknown text block")
        with self.db:
            self.db.execute("UPDATE text_blocks SET bbox_json=?,rotation=?,revision=revision+1 WHERE id=?",
                            (json.dumps(bbox), rotation, block_id))
            history.record("text_blocks", block_id, before, "geometry")

    def delete(self, block_id: str) -> None:
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        if before is None:
            raise ValueError("Unknown text block")
        with self.db:
            self.db.execute("UPDATE text_blocks SET active=0,revision=revision+1 WHERE id=?", (block_id,))
            history.record("text_blocks", block_id, before, "delete_block")

    def duplicate(self, block_id: str) -> str:
        original = self.db.execute("SELECT * FROM text_blocks WHERE id=?", (block_id,)).fetchone()
        if original is None:
            raise ValueError("Unknown text block")
        page = self.db.execute("SELECT page_uid FROM pages WHERE id=?", (original["page_id"],)).fetchone()
        rows = self.db.execute("SELECT text_uid,sequence FROM text_blocks WHERE page_id=?", (original["page_id"],)).fetchall()
        number = max(int(row["text_uid"].rsplit("-T", 1)[1]) for row in rows) + 1
        sequence = max(row["sequence"] for row in rows) + 1
        new_id = str(uuid.uuid4())
        with self.db:
            self.db.execute("""INSERT INTO text_blocks
                (id,page_id,text_uid,sequence,reading_order,bbox_json,polygon_json,source_text,
                 source_language,ocr_confidence,writing_mode,rotation,region_type,review_status,
                 style_id,erase_data_json,mask_path,active)
                SELECT ?,page_id,?,?,?,bbox_json,polygon_json,source_text,source_language,
                       ocr_confidence,writing_mode,rotation,region_type,review_status,style_id,
                       erase_data_json,NULL,1 FROM text_blocks WHERE id=?""",
                (new_id, f"{page['page_uid']}-T{number:03d}", sequence, original["reading_order"]+1, block_id))
            HistoryService(self.db).record("text_blocks", new_id, None, "duplicate_block")
        return new_id

    def translation(self, block_id: str, language: str = "zh_CN") -> dict | None:
        row = self.db.execute("SELECT * FROM translations WHERE text_block_id=? AND language=?",
                              (block_id, language)).fetchone()
        return dict(row) if row else None

    def save_translation(self, block_id: str, text: str, notes: str = "", language: str = "zh_CN") -> None:
        existing = self.translation(block_id, language)
        history = HistoryService(self.db)
        before = history.snapshot("translations", existing["id"]) if existing else None
        translation_id = existing["id"] if existing else str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.db:
            if existing:
                self.db.execute("""UPDATE translations SET text=?,notes=?,status=?,revision=revision+1,
                    updated_at=? WHERE id=?""", (text, notes, "human_edited" if text.strip() else "empty",
                                               timestamp, existing["id"]))
            else:
                self.db.execute("""INSERT INTO translations
                    (id,text_block_id,language,text,notes,status,updated_at,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                    (translation_id, block_id, language, text, notes,
                     "human_edited" if text.strip() else "empty", timestamp, timestamp))
            self.db.execute("UPDATE text_blocks SET typeset_status=? WHERE id=?",
                            ("ready" if text.strip() else "pending", block_id))
            history.record("translations", translation_id, before, "translation")
