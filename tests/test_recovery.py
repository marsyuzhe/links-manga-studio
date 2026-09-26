import sqlite3

from app.diagnostics import collect
from app.session import SessionGuard


def test_project_backup_and_local_diagnostics(project_factory, tmp_path):
    project = project_factory()
    backup = project.backup_project()
    assert (backup / "project.json").is_file()
    assert (backup / "project.sqlite3").is_file()
    with sqlite3.connect(backup / "project.sqlite3") as db:
        assert db.execute("SELECT id FROM projects").fetchone()[0] == project.connection.execute(
            "SELECT id FROM projects").fetchone()[0]
    info = collect(project.path, tmp_path / "app.log")
    assert info["OCR Model Installed"] == "True"
    assert info["CUDA Available"] in ("True", "False")
    assert info["Project Path"] == str(project.path)


def test_crash_marker_detects_unclean_session(tmp_path):
    first = SessionGuard(tmp_path)
    assert not first.previous_unclean
    first.start()
    second = SessionGuard(tmp_path)
    assert second.previous_unclean
    second.close()
    assert not SessionGuard(tmp_path).previous_unclean
