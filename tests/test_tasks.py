from threading import Event

from app.database.database import connect
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.pages.page_service import PageService
from app.tasks.service import TaskService
from conftest import make_image


def test_task_pause_resume_failure_and_crash(project_factory, tmp_path):
    project = project_factory()
    sources = [make_image(tmp_path / f"{index}.png", seed=index) for index in range(3)]
    importer = ImageImporter(project.path)
    assert importer.commit(importer.validate(scan_files(sources))) == 3
    ids = [p["id"] for p in PageService(project.connection, project.path).list_pages()]
    tasks = TaskService(project.connection)
    task_id = tasks.create("ocr", ids, max_attempts=2)
    stop = Event()
    seen = []

    def first(page_id):
        seen.append(page_id)
        stop.set()

    assert tasks.run(task_id, first, stop)["status"] == "paused"
    assert seen == ids[:1]
    with project.connection:
        project.connection.execute("UPDATE tasks SET status='running' WHERE id=?", (task_id,))
        project.connection.execute("UPDATE task_items SET status='running' WHERE page_id=?", (ids[1],))
    project.connection.close()
    project.connection = connect(project.path / "project.sqlite3")
    tasks = TaskService(project.connection)
    assert tasks.recover_interrupted() == 1
    assert tasks.summary(task_id)["status"] == "interrupted"

    def remaining(page_id):
        seen.append(page_id)
        if page_id == ids[1]:
            raise ValueError("bad page")

    result = tasks.run(task_id, remaining)
    assert result["status"] == "failed"
    assert result["completed"] == 2
    assert seen.count(ids[0]) == 1
    assert tasks.run(task_id, lambda page_id: seen.append(page_id))["status"] == "completed"
    assert seen.count(ids[1]) == 2
    assert tasks.summary(task_id)["completed"] == 3
