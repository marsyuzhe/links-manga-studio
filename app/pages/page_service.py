"""Immediate transactional page edits and conservative source relocation."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
from app.importers.folder_importer import scan_folder
from app.importers.image_importer import sha256


class PageService:
    """Own page metadata edits; display order may change while page_uid remains permanent."""
    def __init__(self, connection: sqlite3.Connection, project: Path) -> None:
        self.connection = connection
        self.project = project

    def list_pages(self) -> list[dict]:
        rows = self.connection.execute("""SELECT p.*,s.kind AS source_kind,s.original_path,s.stored_path,s.sha256,
            EXISTS(SELECT 1 FROM text_blocks t WHERE t.page_id=p.id AND t.active=1 AND
              (t.erase_data_json!='{}' OR t.mask_path IS NOT NULL OR EXISTS(
                SELECT 1 FROM translations x WHERE x.text_block_id=t.id AND x.text!=''))) AS has_render_edits,
            s.metadata_json,s.size_bytes,s.status AS source_status FROM pages p
            JOIN source_files s ON s.id=p.source_file_id WHERE p.deleted_at IS NULL
            ORDER BY p.display_order""").fetchall()
        progress = {row["page_id"]: dict(row) for row in self.connection.execute("""
            SELECT t.page_id, count(*) AS text_count,
              sum(CASE WHEN x.id IS NOT NULL AND trim(x.text)<>'' THEN 1 ELSE 0 END) AS translated_count,
              sum(CASE WHEN t.erase_status='erased' THEN 1 ELSE 0 END) AS erased_count,
              sum(CASE WHEN t.typeset_status='ready' AND x.id IS NOT NULL AND trim(x.text)<>'' THEN 1 ELSE 0 END) AS typeset_count
            FROM text_blocks t LEFT JOIN translations x ON x.text_block_id=t.id
            WHERE t.active=1 GROUP BY t.page_id""")}
        result = []
        for row in rows:
            page = dict(row)
            page["metadata"] = json.loads(page.pop("metadata_json"))
            page["filename"] = page["metadata"].get("original_filename", Path(page["original_path"]).name)
            page["path"] = str(self.project / page["stored_path"]) if page["stored_path"] else page["original_path"]
            page.update(progress.get(page["id"], {"text_count": 0, "translated_count": 0,
                                                 "erased_count": 0, "typeset_count": 0}))
            result.append(page)
        return result

    def set_status(self, page_id: str, status: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE pages SET status=? WHERE id=?", (status, page_id))
            self.connection.execute("UPDATE source_files SET status=? WHERE id=(SELECT source_file_id FROM pages WHERE id=?)",
                                    ("available" if status == "ready" else status, page_id))

    def set_label(self, page_id: str, label: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE pages SET label=?,revision=revision+1 WHERE id=?", (label, page_id))

    def move(self, page_id: str, delta: int) -> None:
        pages = self.list_pages()
        index = next(i for i, page in enumerate(pages) if page["id"] == page_id)
        target = index + delta
        if target < 0 or target >= len(pages):
            return
        a, b = pages[index], pages[target]
        with self.connection:
            self.connection.execute("UPDATE pages SET display_order=-display_order WHERE id IN (?,?)", (a["id"], b["id"]))
            self.connection.execute("UPDATE pages SET display_order=?,revision=revision+1 WHERE id=?", (b["display_order"], a["id"]))
            self.connection.execute("UPDATE pages SET display_order=?,revision=revision+1 WHERE id=?", (a["display_order"], b["id"]))

    def health_check(self) -> list[dict]:
        """Cheap existence checks only; no startup image decoding or hashing."""
        pages = self.list_pages()
        for page in pages:
            exists = Path(page["path"]).is_file()
            if not exists:
                self.set_status(page["id"], "missing")
            elif page["status"] == "missing":
                self.set_status(page["id"], "ready")
        return self.list_pages()

    def relocate(self, root: Path, progress=lambda *a: None) -> dict:
        paths = scan_folder(root).paths
        by_name: dict[str, list[Path]] = {}
        for path in paths:
            by_name.setdefault(path.name.casefold(), []).append(path)
        updated, unresolved = 0, []
        pages = self.list_pages()
        changes: dict[str, Path] = {}
        for index, page in enumerate(pages, 1):
            progress(index, len(pages), f"Relocating {page['filename']}")
            if page["stored_path"] or Path(page["path"]).is_file():
                continue
            relative = Path(page["metadata"].get("relative_path", page["filename"]))
            direct = (root / relative).resolve()
            candidates = by_name.get(page["filename"].casefold(), [])
            if direct in candidates:
                candidates = [direct]
            matches = [p for p in candidates if p.stat().st_size == page["size_bytes"] and sha256(p) == page["sha256"]]
            if len(matches) == 1:
                changes[page["source_file_id"]] = matches[0]
                updated += 1
            else:
                unresolved.append(page["page_uid"])
        with self.connection:
            for source_id, path in changes.items():
                metadata = json.loads(self.connection.execute("SELECT metadata_json FROM source_files WHERE id=?", (source_id,)).fetchone()[0])
                metadata.update(mtime_ns=path.stat().st_mtime_ns, relative_path=str(path.relative_to(root.resolve())))
                self.connection.execute("UPDATE source_files SET original_path=?,status='available',metadata_json=? WHERE id=?",
                                        (str(path), json.dumps(metadata, ensure_ascii=False), source_id))
                self.connection.execute("UPDATE pages SET status='ready',revision=revision+1 WHERE source_file_id=?", (source_id,))
        return {"relocated": updated, "unresolved": unresolved}
