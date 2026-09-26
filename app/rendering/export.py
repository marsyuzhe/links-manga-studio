"""Resumable page image export using the same renderer as canvas preview."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from threading import Event

from app.database.database import connect
from app.pages.page_service import PageService
from app.rendering.renderer import PageRenderer
from app.tasks.service import TaskService


FORMATS = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


def export_pages(project: Path, page_ids: list[str] | None = None, fmt: str = "png",
                 task_id: str | None = None, progress=lambda *a: None,
                 stop: Event | None = None) -> dict:
    if fmt not in FORMATS:
        raise ValueError("Unsupported image format")
    db = connect(project / "project.sqlite3")
    try:
        tasks = TaskService(db)
        if task_id is None:
            if not page_ids:
                raise ValueError("No pages selected")
            task_id = tasks.create("final_export", page_ids)
        pages = {page["id"]: page for page in PageService(db, project).list_pages()}
        renderer = PageRenderer(db, project)
        output = project / "exports" / f"render_{task_id[:8]}"
        output.mkdir(parents=True, exist_ok=True)
        total = tasks.summary(task_id)["total"]

        def process(page_id):
            page = pages[page_id]
            image = renderer.render_page(page)
            target = output / f"{page['page_uid']}.{fmt}"
            temporary = output / f"{uuid.uuid4().hex[:12]}.tmp"
            try:
                if not image.save(str(temporary), FORMATS[fmt], 90 if fmt != "png" else -1):
                    raise OSError(f"Cannot encode {fmt.upper()} image")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            progress(tasks.summary(task_id)["completed"] + 1, total, f"Export {page['page_uid']}")

        result = tasks.run(task_id, process, stop)
        result.update(task_id=task_id, output=str(output))
        return result
    finally:
        db.close()
