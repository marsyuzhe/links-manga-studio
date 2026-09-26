"""Phase 0 acceptance checks."""
import json
import logging
import os
import sqlite3
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.database.schema import VERSION
from app.diagnostics import collect
from app.logging_setup import setup_logging
from app.project import DIRS, ProjectError, ProjectService
from app.ui.window import MainWindow


def test_create_open_chinese_recent_and_schema(tmp_path):
    config_path = tmp_path / "settings" / "config.json"
    service = ProjectService(Config(config_path))
    for name, mode in (("English", "copy"), ("测试漫画", "reference")):
        path = service.create_project(tmp_path, name, mode)
        assert path.exists()
        assert all((path / item).is_dir() for item in DIRS)
        metadata = json.loads((path / "project.json").read_text(encoding="utf-8"))
        row = service.connection.execute("SELECT * FROM projects").fetchone()
        assert metadata["project_uuid"] == row["id"]
        assert metadata["name"] == row["name"]
        assert metadata["source_mode"] == row["source_mode"]
        assert service.connection.execute("PRAGMA user_version").fetchone()[0] == VERSION
        assert service.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert service.connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        tables = {r[0] for r in service.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"projects", "source_files", "pages", "batches", "batch_pages", "text_blocks",
                "translations", "styles", "tasks", "task_items", "history", "document_exports",
                "document_imports", "ocr_runs"} <= tables
        service.close_project()
        service.open_project(path)
        assert service.path == path.resolve()
        service.close_project()
    assert len(Config(config_path).recent_projects) == 2
    with pytest.raises(ProjectError, match="already exists"):
        service.create_project(tmp_path, "English")


def test_bad_parent_and_mismatch(tmp_path):
    service = ProjectService(Config(tmp_path / "config.json"))
    with pytest.raises(ProjectError, match="Cannot create project"):
        service.create_project(tmp_path / "missing_parent", "NoPermission")
    path = service.create_project(tmp_path, "Mismatch")
    service.close_project()
    metadata = json.loads((path / "project.json").read_text(encoding="utf-8"))
    metadata["project_uuid"] = "wrong"
    (path / "project.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ProjectError, match="does not match"):
        service.open_project(path)


def test_permission_error_is_explicit(tmp_path, monkeypatch):
    service = ProjectService(Config(tmp_path / "config.json"))
    original_mkdir = Path.mkdir

    def deny_project_directory(path, *args, **kwargs):
        if path.name == "Protected.lmw":
            raise PermissionError("Access denied")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_project_directory)
    with pytest.raises(ProjectError, match="Access denied"):
        service.create_project(tmp_path, "Protected")


def test_logging_traceback_and_diagnostics(tmp_path):
    log = setup_logging(tmp_path / "logs")
    try:
        raise RuntimeError("controlled test error")
    except RuntimeError:
        logging.exception("Controlled error")
    logging.shutdown()
    content = log.read_text(encoding="utf-8")
    assert "Traceback" in content and "controlled test error" in content
    info = collect(tmp_path, log)
    assert info["App Version"] and info["Python Version"] and info["SQLite Version"]
    assert info["Project Path"] == str(tmp_path)
    assert info["Log Path"] == str(log)


def test_window_start_close_and_recent_persistence(qtbot, tmp_path):
    config_path = tmp_path / "config.json"
    log = setup_logging(tmp_path / "logs")
    service = ProjectService(Config(config_path))
    window = MainWindow(service, log)
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
    assert window.stack.currentIndex() == 0
    path = service.create_project(tmp_path, "GUI")
    window._project_opened()
    assert window.stack.currentIndex() == 1
    window.close_project()
    assert window.stack.currentIndex() == 0
    window.close()
    next_window = MainWindow(ProjectService(Config(config_path)), log)
    qtbot.addWidget(next_window)
    assert str(path) in [next_window.recent.item(i).data(Qt.ItemDataRole.UserRole)
                         for i in range(next_window.recent.count())]
    next_window.close()
