import json
import sqlite3

from app.project import ProjectService
from app.config import Config
from app.database.schema import VERSION


def test_v1_migrates_with_backup_and_metadata_sync(project_factory, tmp_path):
    service = project_factory()
    path = service.path
    service.close_project()
    database = path / "project.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("ALTER TABLE history DROP COLUMN undone")
        db.execute("UPDATE projects SET schema_version=1")
        db.execute("PRAGMA user_version=1")
    metadata = json.loads((path / "project.json").read_text(encoding="utf-8"))
    metadata["schema_version"] = 1
    (path / "project.json").write_text(json.dumps(metadata), encoding="utf-8")
    service.open_project(path)
    assert service.connection.execute("PRAGMA user_version").fetchone()[0] == VERSION
    assert json.loads((path / "project.json").read_text(encoding="utf-8"))["schema_version"] == VERSION
    assert len(list((path / "backups").glob("before-schema-v2-*.sqlite3"))) == 1
