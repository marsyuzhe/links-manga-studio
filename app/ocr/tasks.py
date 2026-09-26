"""Long-running OCR jobs use the project's persistent per-page task records."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from app.database.database import connect
from app.ocr.pipeline import OCRPipeline, RapidBackend
from app.pages.page_service import PageService
from app.tasks.service import TaskService


def run_ocr_task(project: Path, page_ids: list[str] | None = None, task_id: str | None = None,
                 progress=lambda *a: None, stop: Event | None = None) -> dict:
    connection = connect(project / "project.sqlite3")
    try:
        tasks = TaskService(connection)
        if task_id is None:
            if not page_ids:
                raise ValueError("No pages selected for OCR")
            task_id = tasks.create("ocr", page_ids)
        pages = {page["id"]: page for page in PageService(connection, project).list_pages()}
        backend = RapidBackend()
        pipeline = OCRPipeline(connection, project, backend)
        total = tasks.summary(task_id)["total"]

        def process(page_id):
            if page_id not in pages:
                raise FileNotFoundError(f"Page is missing from project: {page_id}")
            pipeline.process_page(pages[page_id])
            done = tasks.summary(task_id)["completed"] + 1
            progress(done, total, f"OCR {pages[page_id]['page_uid']}")

        result = tasks.run(task_id, process, stop)
        result["task_id"] = task_id
        return result
    finally:
        connection.close()
