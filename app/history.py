"""Database-backed undo/redo for immediate project edits."""
from __future__ import annotations

import json
import sqlite3
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone


TABLES = {"text_blocks", "translations", "styles", "text_style_presets", "glossary", "character_notes"}


class HistoryService:
    """Record snapshots inside the caller's edit transaction, never in a later autosave."""
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def snapshot(self, table: str, row_id: str) -> dict | None:
        if table not in TABLES:
            raise ValueError("Unsupported history target")
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
        return dict(row) if row else None

    def record(self, table: str, row_id: str, before: dict | None, command: str = "edit",
               group_id: str | None = None) -> None:
        after = self.snapshot(table, row_id)
        if before == after:
            return
        project_id = self.db.execute("SELECT id FROM projects").fetchone()[0]
        self.db.execute("UPDATE history SET undone=2 WHERE undone=1")
        self.db.execute("""INSERT INTO history
            (id,project_id,command_type,target_type,target_id,before_json,after_json,created_at,group_id)
            VALUES(?,?,?,?,?,?,?,?,?)""", (str(uuid.uuid4()), project_id, command, table, row_id,
            json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(), group_id))

    def record_mask(self, block_id: str, target: Path, before: Path | None, after: Path) -> None:
        project_id = self.db.execute("SELECT id FROM projects").fetchone()[0]
        root = Path(self.db.execute("PRAGMA database_list").fetchone()[2]).parent
        relative_target = str(target.relative_to(root))
        self.db.execute("UPDATE history SET undone=2 WHERE undone=1")
        self.db.execute("""INSERT INTO history
            (id,project_id,command_type,target_type,target_id,before_json,after_json,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", (str(uuid.uuid4()), project_id, "mask", "mask_file", block_id,
            json.dumps({"target": relative_target, "snapshot": str(before.relative_to(root)) if before else None}),
            json.dumps({"target": relative_target, "snapshot": str(after.relative_to(root))}),
            datetime.now(timezone.utc).isoformat()))

    def _restore(self, table: str, row_id: str, state: dict | None) -> None:
        translation_owner = None
        if table == "translations":
            current = self.snapshot(table, row_id)
            translation_owner = (state or current or {}).get("text_block_id")
        if table == "mask_file":
            root = Path(self.db.execute("PRAGMA database_list").fetchone()[2]).parent
            target = (root / state["target"]).resolve()
            if not target.is_relative_to((root / "masks").resolve()):
                raise ValueError("Invalid mask history target")
            if state["snapshot"]:
                snapshot = (root / state["snapshot"]).resolve()
                if not snapshot.is_relative_to((root / "masks" / ".history").resolve()):
                    raise ValueError("Invalid mask history snapshot")
                shutil.copy2(snapshot, target)
            else:
                target.unlink(missing_ok=True)
            return
        if table not in TABLES:
            raise ValueError("Unsupported history target")
        if state is None:
            self.db.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
        elif self.snapshot(table, row_id) is None:
            columns = list(state)
            self.db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                            [state[column] for column in columns])
        else:
            columns = [key for key in state if key != "id"]
            self.db.execute(f"UPDATE {table} SET {','.join(f'{key}=?' for key in columns)} WHERE id=?",
                            [state[column] for column in columns] + [row_id])
        if translation_owner:
            translated = self.db.execute("SELECT 1 FROM translations WHERE text_block_id=? AND trim(text)<>'' LIMIT 1",
                                         (translation_owner,)).fetchone()
            self.db.execute("UPDATE text_blocks SET typeset_status=? WHERE id=?",
                            ("ready" if translated else "pending", translation_owner))

    def undo(self) -> bool:
        row = self.db.execute("SELECT * FROM history WHERE undone=0 ORDER BY rowid DESC LIMIT 1").fetchone()
        if row is None:
            return False
        rows = (self.db.execute("SELECT * FROM history WHERE undone=0 AND group_id=? ORDER BY rowid DESC",
                                (row["group_id"],)).fetchall() if row["group_id"] else [row])
        with self.db:
            for item in rows:
                self._restore(item["target_type"], item["target_id"], json.loads(item["before_json"]))
                self.db.execute("UPDATE history SET undone=1 WHERE id=?", (item["id"],))
        return True

    def redo(self) -> bool:
        row = self.db.execute("SELECT * FROM history WHERE undone=1 ORDER BY rowid LIMIT 1").fetchone()
        if row is None:
            return False
        rows = (self.db.execute("SELECT * FROM history WHERE undone=1 AND group_id=? ORDER BY rowid",
                                (row["group_id"],)).fetchall() if row["group_id"] else [row])
        with self.db:
            for item in rows:
                self._restore(item["target_type"], item["target_id"], json.loads(item["after_json"]))
                self.db.execute("UPDATE history SET undone=0 WHERE id=?", (item["id"],))
        return True

    def next_command(self, redo: bool = False) -> str | None:
        row = self.db.execute("SELECT command_type FROM history WHERE undone=? ORDER BY rowid " +
                              ("ASC" if redo else "DESC") + " LIMIT 1", (1 if redo else 0,)).fetchone()
        return row[0] if row else None
