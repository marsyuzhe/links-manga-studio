"""UID-safe page context, immediate transactions and one undo group per page."""
from __future__ import annotations
import json
import uuid
from app.history import HistoryService
from app.ocr.review import TextBlockService
from app.tasks.service import now
from .profiles import TranslationError
from .providers import PROMPT_VERSION, validate_output

DEFAULTS = {"target_language": "Simplified Chinese", "preset": "natural", "context_pages": 1, "glossary_enabled": True, "characters_enabled": True,
            "instructions": "Keep names and honorifics. Preserve ellipses. Do not invent information."}


class TranslationService:
    """Prepare text/context and commit checked results; HTTP and secrets belong to providers."""
    def __init__(self, db):
        self.db = db
        self.project_id = db.execute("SELECT id FROM projects").fetchone()[0]

    def settings(self) -> dict:
        row = self.db.execute("SELECT * FROM project_translation_settings WHERE project_id=?", (self.project_id,)).fetchone()
        return {**DEFAULTS, **(json.loads(row["settings_json"]) if row else {}),
                "provider_profile_id": row["provider_profile_id"] if row else None}

    def save_settings(self, values):
        safe = {k: values[k] for k in DEFAULTS if k in values}
        if not 0 <= int(safe.get("context_pages", 1)) <= 10:
            raise TranslationError("invalid_context")
        profile_id = values.get("provider_profile_id", self.settings()["provider_profile_id"])
        merged = {**self.settings(), **safe}
        merged.pop("provider_profile_id", None)
        with self.db:
            self.db.execute("""INSERT INTO project_translation_settings VALUES(?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET provider_profile_id=excluded.provider_profile_id,
                settings_json=excluded.settings_json""", (self.project_id, profile_id, json.dumps(merged, ensure_ascii=False)))

    def replace_terms(self, terms, characters):
        with self.db:
            self.db.execute("DELETE FROM glossary WHERE project_id=?", (self.project_id,))
            self.db.execute("DELETE FROM character_notes WHERE project_id=?", (self.project_id,))
            for row in terms:
                if not row.get("source_term") or not row.get("target_term"):
                    raise TranslationError("invalid_glossary")
                self.db.execute("INSERT INTO glossary(id,project_id,source_term,target_term,note,case_sensitive,exact_match) VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), self.project_id,
                    row["source_term"], row["target_term"], row.get("note", ""),
                    bool(row.get("case_sensitive", False)), bool(row.get("exact_match", True))))
            for row in characters:
                if not row.get("name"):
                    raise TranslationError("invalid_glossary")
                self.db.execute("INSERT INTO character_notes(id,project_id,name,translated_name,description,speech_style) VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), self.project_id,
                    row["name"], row.get("translated_name", ""), row.get("description", ""), row.get("speech_style", "")))

    def terms(self, table: str) -> list[dict]:
        if table not in ("glossary", "character_notes"):
            raise ValueError(table)
        return [dict(r) for r in self.db.execute(f"SELECT * FROM {table} WHERE project_id=? ORDER BY rowid", (self.project_id,))]

    def prepare(self, page_id, options=None, context=True):
        options = options or {}
        review = TextBlockService(self.db)
        targets = []
        snapshots = {}
        for block in review.for_page(page_id):
            if options.get("block_ids") and block["id"] not in options["block_ids"]:
                continue
            if not block["source_text"].strip():
                continue
            existing = review.translation(block["id"])
            if existing and existing["text"].strip():
                status = existing["status"]
                if status == "ai_draft":
                    if not options.get("include_ai_draft"):
                        continue
                elif not options.get("overwrite_protected"):
                    continue
            targets.append({"id": block["text_uid"], "source": block["source_text"]})
            snapshots[block["text_uid"]] = {"block": block, "translation": existing}
        if not context:
            return {"target": targets}, snapshots
        settings = {**self.settings(), **options.get("settings", {})}
        context_count = int(settings["context_pages"])
        pages = [r[0] for r in self.db.execute("SELECT id FROM pages WHERE deleted_at IS NULL ORDER BY display_order")]
        if page_id not in pages:
            raise TranslationError("page_missing")
        position = pages.index(page_id)
        context = []
        # Neighbor pages inform phrasing only; snapshots contain exclusively writable target UIDs.
        for pid in pages[max(0, position-context_count):position+context_count+1]:
            if pid != page_id:
                context.append({"page_uid": self.db.execute("SELECT page_uid FROM pages WHERE id=?", (pid,)).fetchone()[0],
                    "blocks": [{"id": b["text_uid"], "source": b["source_text"]} for b in review.for_page(pid)]})
        terms = [{k: v for k, v in row.items() if k not in ("id", "project_id")} for row in self.terms("glossary")]
        # Send terminology, not project/database identity; optional injection stays task-controlled.
        characters = [{k: v for k, v in row.items() if k not in ("id", "project_id")} for row in self.terms("character_notes")]
        return {"target": targets, "context": context, "target_language": settings["target_language"],
                "preset": settings["preset"], "instructions": settings["instructions"],
                "glossary": terms if settings["glossary_enabled"] else [], "characters": characters if settings["characters_enabled"] else []}, snapshots

    def preview(self, page_ids, options=None):
        counts = [(pid, len(self.prepare(pid, options, context=False)[0]["target"])) for pid in page_ids]
        return {"pages": sum(count > 0 for _, count in counts), "blocks": sum(count for _, count in counts)}

    def apply(self, snapshots, result, profile):
        values = validate_output([{"id": uid, "translation": text} for uid, text in result.translations.items()], snapshots)
        history = HistoryService(self.db)
        group = str(uuid.uuid4())
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # Re-check after HTTP completes, inside the write transaction. Reject stale responses.
            for uid, snap in snapshots.items():
                block = snap["block"]
                current = self.db.execute("SELECT * FROM text_blocks WHERE id=? AND active=1", (block["id"],)).fetchone()
                current_translation = TextBlockService(self.db).translation(block["id"])
                if current is None or dict(current) != block or current_translation != snap["translation"]:
                    raise TranslationError("stale_translation")
            for uid, snap in snapshots.items():
                block, previous = snap["block"], snap["translation"]
                tid = previous["id"] if previous else str(uuid.uuid4())
                before = history.snapshot("translations", tid)
                timestamp = now()
                self.db.execute("""INSERT INTO translations(id,text_block_id,language,text,status,source,updated_at,
                    created_at,provider_profile_id,provider,model,prompt_version)
                    VALUES(?,?,'zh_CN',?,'ai_draft',?,?,?,?,?,?,?)
                    ON CONFLICT(text_block_id,language) DO UPDATE SET text=excluded.text,status='ai_draft',
                    source=excluded.source,updated_at=excluded.updated_at,provider_profile_id=excluded.provider_profile_id,
                    provider=excluded.provider,model=excluded.model,prompt_version=excluded.prompt_version,
                    revision=translations.revision+1""", (tid, block["id"], values[uid],
                    "ai_local" if profile.local else "ai_api", timestamp, timestamp, profile.id,
                    profile.provider_type, profile.model, PROMPT_VERSION))
                self.db.execute("UPDATE text_blocks SET typeset_status='ready' WHERE id=?", (block["id"],))
                history.record("translations", tid, before, "ai_translation_page", group)

    def mark_reviewed(self, block_id):
        translation = TextBlockService(self.db).translation(block_id)
        if not translation or not translation["text"].strip():
            raise TranslationError("empty_translation")
        history = HistoryService(self.db)
        with self.db:
            self.db.execute("UPDATE translations SET status='reviewed',revision=revision+1,updated_at=? WHERE id=?",
                            (now(), translation["id"]))
            history.record("translations", translation["id"], translation, "translation_review")
