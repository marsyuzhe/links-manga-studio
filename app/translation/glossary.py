"""Immediate project terminology edits over the existing glossary data layer."""
import csv
import io
import uuid
from app.tasks.service import now
from app.history import HistoryService
from app.translation.service import TranslationService

CATEGORIES = ("character", "place", "organization", "item", "skill", "other")

class GlossaryService:
    def __init__(self, db):
        self.db = db
        self.service = TranslationService(db)
        self.project_id = self.service.project_id

    def terms(self, query="", category="", recent=False):
        rows = self.service.terms("glossary")
        query = query.casefold()
        rows = [r for r in rows if (not category or r["category"] == category) and
                (not query or query in " ".join(str(r[k]) for k in ("source_term", "target_term", "note")).casefold())]
        return sorted(rows, key=lambda r:r["updated_at"] if recent else r["source_term"].casefold(), reverse=recent)

    def save(self, values, term_id=None):
        source, target = values.get("source_term", "").strip(), values.get("target_term", "").strip()
        if not source or not target: raise ValueError("原文和固定译名不能为空 / Source and translation are required")
        category = values.get("category", "other")
        if category not in CATEGORIES: category = "other"
        term_id = term_id or str(uuid.uuid4())
        with self.db:
            history=HistoryService(self.db);before=history.snapshot("glossary",term_id)
            self.db.execute("""INSERT INTO glossary(id,project_id,source_term,target_term,note,category,updated_at,case_sensitive,exact_match)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET source_term=excluded.source_term,
                target_term=excluded.target_term,note=excluded.note,category=excluded.category,updated_at=excluded.updated_at""",
                (term_id,self.project_id,source,target,values.get("note", ""),category,now(),bool(values.get("case_sensitive",False)),bool(values.get("exact_match",True))))
            history.record("glossary",term_id,before,"glossary_edit")
        return term_id

    def delete(self, term_id):
        with self.db:
            history=HistoryService(self.db);before=history.snapshot("glossary",term_id)
            self.db.execute("DELETE FROM glossary WHERE id=? AND project_id=?", (term_id,self.project_id))
            history.record("glossary",term_id,before,"glossary_delete")

    def conflicts(self):
        groups = {}
        for r in self.terms(): groups.setdefault(r["source_term"].casefold(),set()).add(r["target_term"])
        return {source for source, targets in groups.items() if len(targets)>1}

    def import_csv(self, text):
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        if not {"source", "target"}.issubset(reader.fieldnames or []): raise ValueError("CSV requires source,target,category,note")
        result = {"success":0,"skipped":0,"conflicts":0}
        known = {(r["source_term"],r["target_term"]) for r in self.terms()}
        # One transaction for the whole CSV, including validation and conflict accounting.
        with self.db:
            history=HistoryService(self.db);group=str(uuid.uuid4())
            for row in reader:
                source,target = (row.get("source") or "").strip(),(row.get("target") or "").strip()
                if not source or not target or (source,target) in known:
                    result["skipped"]+=1;continue
                if any(s.casefold()==source.casefold() and t!=target for s,t in known):result["conflicts"]+=1
                tid=str(uuid.uuid4())
                self.db.execute("INSERT INTO glossary(id,project_id,source_term,target_term,category,note,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (tid,self.project_id,source,target,row.get("category") if row.get("category") in CATEGORIES else "other",row.get("note") or "",now()))
                history.record("glossary",tid,None,"glossary_csv",group)
                known.add((source,target));result["success"]+=1
        return result

    def export_csv(self):
        output=io.StringIO();writer=csv.writer(output);writer.writerow(("source","target","category","note"))
        for r in self.terms():
            # Neutralize spreadsheet formulas while preserving ordinary manga terminology.
            writer.writerow(["'"+v if v.startswith(("=","+","-","@")) else v for v in (r["source_term"],r["target_term"],r["category"],r["note"])])
        return output.getvalue()

    def characters(self):return self.service.terms("character_notes")

    def save_character(self, values, character_id=None):
        if not values.get("name", "").strip():raise ValueError("人物姓名不能为空 / Name is required")
        character_id=character_id or str(uuid.uuid4())
        with self.db:
            history=HistoryService(self.db);before=history.snapshot("character_notes",character_id)
            self.db.execute("""INSERT INTO character_notes(id,project_id,name,translated_name,description,speech_style,note)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,translated_name=excluded.translated_name,
                description=excluded.description,speech_style=excluded.speech_style,note=excluded.note""",
                (character_id,self.project_id,*[values.get(k, "").strip() for k in ("name","translated_name","description","speech_style","note")]))
            history.record("character_notes",character_id,before,"character_edit")
        return character_id

    def delete_character(self, character_id):
        with self.db:
            history=HistoryService(self.db);before=history.snapshot("character_notes",character_id)
            self.db.execute("DELETE FROM character_notes WHERE id=? AND project_id=?",(character_id,self.project_id))
            history.record("character_notes",character_id,before,"character_delete")
