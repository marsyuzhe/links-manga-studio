"""Explicit batch membership; display order changes never alter membership."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone


class BatchService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def create_for_unassigned(self, size: int | None = None) -> list[str]:
        project = self.db.execute("SELECT id,batch_size FROM projects").fetchone()
        size = size or project["batch_size"]
        if not 1 <= size <= 1000:
            raise ValueError("Batch size must be 1–1000")
        pages = self.db.execute("""SELECT id FROM pages WHERE deleted_at IS NULL AND project_id=?
            AND id NOT IN (SELECT page_id FROM batch_pages) ORDER BY display_order""", (project["id"],)).fetchall()
        if not pages:
            return []
        next_number = self.db.execute("SELECT COALESCE(MAX(batch_number),0)+1 FROM batches").fetchone()[0]
        created = []
        with self.db:
            self.db.execute("UPDATE projects SET batch_size=? WHERE id=?", (size, project["id"]))
            for index in range(0, len(pages), size):
                batch_id = str(uuid.uuid4())
                created.append(batch_id)
                self.db.execute("INSERT INTO batches(id,project_id,batch_number,created_at) VALUES(?,?,?,?)",
                                (batch_id, project["id"], next_number + len(created) - 1,
                                 datetime.now(timezone.utc).isoformat()))
                self.db.executemany("INSERT INTO batch_pages(batch_id,page_id,position) VALUES(?,?,?)",
                                    [(batch_id, row["id"], position) for position, row in enumerate(pages[index:index+size], 1)])
        return created

    def list_batches(self) -> list[dict]:
        return [dict(row) for row in self.db.execute("""SELECT b.*,COUNT(bp.page_id) AS page_count
            FROM batches b LEFT JOIN batch_pages bp ON bp.batch_id=b.id
            GROUP BY b.id ORDER BY b.batch_number""")]

    def page_ids(self, batch_id: str) -> list[str]:
        return [row[0] for row in self.db.execute("SELECT page_id FROM batch_pages WHERE batch_id=? ORDER BY position", (batch_id,))]
