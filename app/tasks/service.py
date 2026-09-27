"""Per-page task state committed after every transition for crash resumption."""
from __future__ import annotations

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Callable


KINDS = {"pdf_render", "thumbnail", "ocr", "word_export", "word_import", "final_render", "final_export", "AI_TRANSLATION"}
STATUSES = {"pending", "running", "paused", "completed", "failed", "interrupted", "cancel_requested", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def create(self, kind: str, page_ids: list[str], batch_id: str | None = None, max_attempts: int = 3,
               options: dict | None = None) -> str:
        if kind not in KINDS or not page_ids or len(set(page_ids)) != len(page_ids) or max_attempts < 1:
            raise ValueError("Invalid task kind, pages or retry limit")
        project_id = self.db.execute("SELECT id FROM projects").fetchone()[0]
        known = {r[0] for r in self.db.execute("SELECT id FROM pages WHERE project_id=? AND deleted_at IS NULL", (project_id,))}
        if not set(page_ids) <= known:
            raise ValueError("Task contains pages outside this project")
        task_id = str(uuid.uuid4())
        timestamp = now()
        with self.db:
            self.db.execute("""INSERT INTO tasks(id,project_id,kind,batch_id,status,total_units,max_attempts,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (task_id, project_id, kind, batch_id, "pending", len(page_ids),
                                                max_attempts, timestamp, timestamp))
            self.db.executemany("INSERT INTO task_items(id,task_id,page_id) VALUES(?,?,?)",
                                [(str(uuid.uuid4()), task_id, page_id) for page_id in page_ids])
            if options is not None:
                self.db.execute("UPDATE tasks SET options_json=? WHERE id=?", (json.dumps(options), task_id))
        return task_id

    def recover_interrupted(self) -> int:
        """Never silently claim an in-flight unit completed after a process crash."""
        with self.db:
            count = self.db.execute("UPDATE tasks SET status='interrupted',updated_at=? WHERE status='running'", (now(),)).rowcount
            self.db.execute("UPDATE task_items SET status='interrupted' WHERE status='running'")
        return count

    def set_status(self, task_id: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(status)
        with self.db:
            self.db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (status, now(), task_id))

    def run(self, task_id: str, process: Callable[[str], None], stop=None) -> dict:
        task = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            raise ValueError("Unknown task")
        if task["status"] in ("completed", "cancelled"):
            return self.summary(task_id)
        self.set_status(task_id, "running")
        rows = self.db.execute("SELECT * FROM task_items WHERE task_id=? ORDER BY rowid", (task_id,)).fetchall()
        for row in rows:
            if row["status"] == "completed" or row["attempts"] >= task["max_attempts"]:
                continue
            if stop is not None and stop.is_set():
                self.set_status(task_id, "paused")
                return self.summary(task_id)
            status = self.db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
            if status == "cancel_requested":
                self.set_status(task_id, "cancelled")
                return self.summary(task_id)
            if status == "paused":
                return self.summary(task_id)
            with self.db:
                self.db.execute("UPDATE task_items SET status='running',attempts=attempts+1,started_at=? WHERE id=?",
                                (now(), row["id"]))
                self.db.execute("UPDATE tasks SET attempts=attempts+1,updated_at=? WHERE id=?", (now(), task_id))
            try:
                process(row["page_id"])
            except Exception as exc:
                with self.db:
                    self.db.execute("UPDATE task_items SET status='failed',last_error=?,finished_at=? WHERE id=?",
                                    (str(exc), now(), row["id"]))
                    self.db.execute("UPDATE tasks SET last_error=?,updated_at=? WHERE id=?", (str(exc), now(), task_id))
            else:
                with self.db:
                    self.db.execute("UPDATE task_items SET status='completed',last_error=NULL,finished_at=? WHERE id=?",
                                    (now(), row["id"]))
                    self.db.execute("UPDATE tasks SET completed_units=completed_units+1,updated_at=? WHERE id=?",
                                    (now(), task_id))
        summary = self.summary(task_id)
        self.set_status(task_id, "completed" if summary["completed"] == summary["total"] else "failed")
        return self.summary(task_id)

    def summary(self, task_id: str) -> dict:
        task = self.db.execute("SELECT status,total_units,completed_units FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            raise ValueError("Unknown task")
        counts = {row[0]: row[1] for row in self.db.execute(
            "SELECT status,COUNT(*) FROM task_items WHERE task_id=? GROUP BY status", (task_id,))}
        return {"status": task["status"], "total": task["total_units"], "completed": task["completed_units"],
                "items": counts}
