"""Project creation and lifecycle."""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .database.database import connect
from .database.schema import VERSION

DIRS = ("sources", "masks", "cache/thumbnails", "cache/pdf_render", "cache/crops",
        "documents", "exports", "backups", "logs", "ocr/raw")


class ProjectError(Exception):
    """A project cannot be created or opened."""


class ProjectService:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.path: Path | None = None
        self.connection: sqlite3.Connection | None = None

    def create_project(self, parent: Path, name: str, source_mode: str = "copy") -> Path:
        name = name.strip()
        if not name or name in (".", "..") or any(c in name for c in '\\/:*?"<>|'):
            raise ProjectError("Enter a valid project name without path separators.")
        if source_mode not in ("copy", "reference"):
            raise ProjectError("Source mode must be copy or reference.")
        path = parent / f"{name}.lmw"
        if path.exists():
            raise ProjectError(f"Project directory already exists: {path}")
        try:
            path.mkdir(parents=False)
            for directory in DIRS:
                (path / directory).mkdir(parents=True)
            project_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            metadata = {"project_uuid": project_id, "name": name, "schema_version": VERSION,
                        "source_mode": source_mode, "created_at": created_at}
            (path / "project.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            connection = connect(path / "project.sqlite3")
            with connection:
                connection.execute("INSERT INTO projects(id,name,schema_version,source_mode,created_at) VALUES(?,?,?,?,?)",
                                   (project_id, name, VERSION, source_mode, created_at))
            from app.styles.project_styles import ProjectStyleService
            ProjectStyleService(connection).ensure_defaults()
            connection.close()
            self.open_project(path)
            return path
        except OSError as exc:
            logging.exception("Cannot create project")
            raise ProjectError(f"Cannot create project at {path}: {exc}") from exc

    def open_project(self, path: Path) -> None:
        self.close_project()
        path = path.resolve()
        try:
            metadata = json.loads((path / "project.json").read_text(encoding="utf-8"))
            connection = connect(path / "project.sqlite3")
            row = connection.execute("SELECT id,name,source_mode,schema_version FROM projects").fetchone()
            if row is None or row["id"] != metadata.get("project_uuid") or row["name"] != metadata.get("name") or row["source_mode"] != metadata.get("source_mode"):
                connection.close()
                raise ProjectError("project.json does not match project.sqlite3")
            if metadata.get("schema_version") != row["schema_version"]:
                metadata["schema_version"] = row["schema_version"]
                temporary = path / "project.json.tmp"
                temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(path / "project.json")
            from app.styles.project_styles import ProjectStyleService
            ProjectStyleService(connection).ensure_defaults()
            self.connection = connection
            self.path = path
            self.config.add_recent(path)
        except (OSError, ValueError, sqlite3.Error) as exc:
            logging.exception("Cannot open project")
            raise ProjectError(f"Cannot open project {path}: {exc}") from exc

    def close_project(self) -> None:
        if self.connection is not None:
            self.connection.close()
        self.connection = None
        self.path = None

    def backup_project(self) -> Path:
        if self.path is None or self.connection is None:
            raise ProjectError("No project is open")
        destination = self.path / "backups" / f"backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        temporary = destination.with_name(destination.name + ".tmp")
        try:
            temporary.mkdir(parents=True)
            backup = sqlite3.connect(temporary / "project.sqlite3")
            try:
                self.connection.backup(backup)
            finally:
                backup.close()
            shutil.copy2(self.path / "project.json", temporary / "project.json")
            if (self.path / "masks").exists():
                shutil.copytree(self.path / "masks", temporary / "masks")
            temporary.rename(destination)
            return destination
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            logging.exception("Project backup failed")
            raise
