"""Inherited project text styles with immediate, undoable SQLite edits."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.history import HistoryService

ROLES = ("speech", "narration", "thought", "sfx", "note", "custom")
DEFAULTS = {
    "speech": {"font": "Microsoft YaHei", "min_size": 18, "max_size": 46,
               "color": "#111111", "alignment": "center", "vertical_alignment": "center", "padding": 8,
               "line_spacing": 1.05, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
    "narration": {"font": "Microsoft YaHei", "min_size": 18, "max_size": 42,
                  "color": "#111111", "alignment": "left", "vertical_alignment": "center", "padding": 8,
                  "line_spacing": 1.1, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
    "thought": {"font": "Microsoft YaHei", "min_size": 18, "max_size": 44,
                "color": "#222222", "alignment": "center", "vertical_alignment": "center", "padding": 8,
                "line_spacing": 1.05, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
    "sfx": {"font": "Microsoft YaHei", "min_size": 20, "max_size": 72,
            "color": "#111111", "alignment": "center", "vertical_alignment": "center", "padding": 4,
            "line_spacing": 1, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
    "note": {"font": "Microsoft YaHei", "min_size": 16, "max_size": 36,
             "color": "#222222", "alignment": "left", "vertical_alignment": "center", "padding": 6,
             "line_spacing": 1.05, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
    "custom": {"font": "Microsoft YaHei", "min_size": 18, "max_size": 46,
               "color": "#111111", "alignment": "center", "vertical_alignment": "center", "padding": 8,
               "line_spacing": 1, "letter_spacing": 0, "auto_fit": True, "writing_mode": "horizontal"},
}


class ProjectStyleService:
    def __init__(self, db):
        self.db = db

    def ensure_defaults(self) -> None:
        project = self.db.execute("SELECT id FROM projects LIMIT 1").fetchone()
        if not project:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            for role in ROLES:
                self.db.execute("""INSERT OR IGNORE INTO text_style_presets
                    (id,project_id,role,name,settings_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?)""", (str(uuid.uuid4()), project["id"], role, role,
                    json.dumps(DEFAULTS[role], ensure_ascii=False), now, now))

    def preset(self, role: str) -> dict:
        self._validate_role(role)
        row = self.db.execute("SELECT * FROM text_style_presets WHERE role=?", (role,)).fetchone()
        if row is None:
            self.ensure_defaults()
            row = self.db.execute("SELECT * FROM text_style_presets WHERE role=?", (role,)).fetchone()
        return dict(row)

    def list_presets(self) -> list[dict]:
        self.ensure_defaults()
        return [dict(row) for row in self.db.execute("SELECT * FROM text_style_presets ORDER BY role")]

    def update_preset(self, role: str, changes: dict) -> None:
        row = self.preset(role)
        before = dict(row)
        settings = json.loads(row["settings_json"])
        original = dict(settings)
        settings.update(changes)
        self._validate_settings(settings)
        if settings == original:
            return
        with self.db:
            self.db.execute("""UPDATE text_style_presets SET settings_json=?,revision=revision+1,updated_at=?
                WHERE id=?""", (json.dumps(settings, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(), row["id"]))
            HistoryService(self.db).record("text_style_presets", row["id"], before, "project_style")

    def set_role(self, block_id: str, role: str) -> None:
        self._validate_role(role)
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        if before is None:
            raise ValueError("Unknown text block")
        if before["style_role"] == role:
            return
        with self.db:
            self.db.execute("UPDATE text_blocks SET style_role=?,revision=revision+1 WHERE id=?", (role, block_id))
            history.record("text_blocks", block_id, before, "style_role")

    def set_override(self, block_id: str, changes: dict) -> None:
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        if before is None:
            raise ValueError("Unknown text block")
        current = json.loads(before["style_override_json"])
        original = dict(current)
        current.update(changes)
        base = json.loads(self.preset(before["style_role"])["settings_json"])
        self._validate_settings(base | current)
        if current == original:
            return
        with self.db:
            self.db.execute("UPDATE text_blocks SET style_override_json=?,revision=revision+1 WHERE id=?",
                            (json.dumps(current, ensure_ascii=False), block_id))
            history.record("text_blocks", block_id, before, "style_override")

    def reset_override(self, block_id: str) -> None:
        history = HistoryService(self.db)
        before = history.snapshot("text_blocks", block_id)
        if before is None:
            raise ValueError("Unknown text block")
        if before["style_override_json"] in ("{}", "") and before["style_id"] is None:
            return
        with self.db:
            self.db.execute("UPDATE text_blocks SET style_override_json='{}',style_id=NULL,revision=revision+1 WHERE id=?",
                            (block_id,))
            history.record("text_blocks", block_id, before, "reset_style")

    def resolve(self, block: dict, legacy_settings: dict | None = None) -> dict:
        role = block.get("style_role") or "speech"
        if role not in ROLES:
            role = "speech"
        result = json.loads(self.preset(role)["settings_json"])
        if legacy_settings:
            result.update(legacy_settings)
        result.update(json.loads(block.get("style_override_json") or "{}"))
        return result

    def apply_to_scope(self, block_id: str, changes: dict, page_ids: list[str] | None = None) -> int:
        """Apply overrides to matching-role blocks in one undo command."""
        source = self.db.execute("SELECT style_role FROM text_blocks WHERE id=? AND active=1", (block_id,)).fetchone()
        if source is None:
            raise ValueError("Unknown text block")
        params: list = [source["style_role"]]
        query = "SELECT id FROM text_blocks WHERE active=1 AND style_role=?"
        if page_ids is not None:
            if not page_ids:
                return 0
            query += " AND page_id IN (" + ",".join("?" for _ in page_ids) + ")"
            params.extend(page_ids)
        ids = [row["id"] for row in self.db.execute(query, params)]
        group = str(uuid.uuid4())
        history = HistoryService(self.db)
        with self.db:
            for target in ids:
                before = history.snapshot("text_blocks", target)
                override = json.loads(before["style_override_json"])
                override.update(changes)
                self.db.execute("UPDATE text_blocks SET style_override_json=?,revision=revision+1 WHERE id=?",
                                (json.dumps(override, ensure_ascii=False), target))
                history.record("text_blocks", target, before, "batch_style", group)
        return len(ids)

    def replace_font(self, old: str, new: str, role: str | None = None) -> int:
        """Replace a missing family in presets and explicit overrides as one undo step."""
        if not old or not new:
            raise ValueError("Select both fonts")
        if role is not None:
            self._validate_role(role)
        group = str(uuid.uuid4())
        history = HistoryService(self.db)
        changed = 0
        with self.db:
            for row in self.db.execute("SELECT * FROM text_style_presets" +
                                       (" WHERE role=?" if role else ""), (role,) if role else ()).fetchall():
                settings = json.loads(row["settings_json"])
                if settings.get("font", "").casefold() != old.casefold():
                    continue
                before = dict(row)
                settings["font"] = new
                self.db.execute("UPDATE text_style_presets SET settings_json=?,revision=revision+1 WHERE id=?",
                                (json.dumps(settings, ensure_ascii=False), row["id"]))
                history.record("text_style_presets", row["id"], before, "replace_font", group)
                changed += 1
            query = "SELECT * FROM text_blocks" + (" WHERE style_role=?" if role else "")
            for row in self.db.execute(query, (role,) if role else ()).fetchall():
                overrides = json.loads(row["style_override_json"])
                if overrides.get("font", "").casefold() != old.casefold():
                    continue
                before = dict(row)
                overrides["font"] = new
                self.db.execute("UPDATE text_blocks SET style_override_json=?,revision=revision+1 WHERE id=?",
                                (json.dumps(overrides, ensure_ascii=False), row["id"]))
                history.record("text_blocks", row["id"], before, "replace_font", group)
                changed += 1
            query = ("""SELECT DISTINCT s.* FROM styles s JOIN text_blocks t ON t.style_id=s.id WHERE t.style_role=?"""
                     if role else "SELECT * FROM styles")
            for row in self.db.execute(query, (role,) if role else ()).fetchall():
                settings = json.loads(row["settings_json"])
                if settings.get("font", "").casefold() != old.casefold():
                    continue
                before = dict(row)
                settings["font"] = new
                self.db.execute("UPDATE styles SET settings_json=?,revision=revision+1 WHERE id=?",
                                (json.dumps(settings, ensure_ascii=False), row["id"]))
                history.record("styles", row["id"], before, "replace_font", group)
                changed += 1
        return changed

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in ROLES:
            raise ValueError("Invalid style role")

    @staticmethod
    def _validate_settings(settings: dict) -> None:
        if not 6 <= int(settings.get("min_size", 18)) <= int(settings.get("max_size", 72)) <= 300:
            raise ValueError("Invalid font size range")
        if not 0 <= float(settings.get("padding", 8)) <= 200:
            raise ValueError("Invalid padding")
