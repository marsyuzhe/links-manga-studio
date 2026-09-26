"""Two-phase import: validate first; stage files, then register all pages atomically."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable

from app.database.database import connect
from app.images.image_loader import ImageLoader
from .folder_importer import ScanResult

Progress = Callable[[int, int, str], None]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ImportCancelled(RuntimeError):
    pass


@dataclass
class Candidate:
    path: Path
    metadata: dict
    digest: str
    duplicate: bool = False


@dataclass
class ImportPreview:
    candidates: list[Candidate] = field(default_factory=list)
    ignored: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duplicates(self) -> int:
        return sum(item.duplicate for item in self.candidates)


class ImageImporter:
    def __init__(self, project: Path) -> None:
        self.project = project
        self.loader = ImageLoader()

    def validate(self, scan: ScanResult, progress: Progress = lambda *a: None,
                 cancel: Event | None = None) -> ImportPreview:
        connection = connect(self.project / "project.sqlite3")
        try:
            rows = connection.execute("SELECT original_path,sha256 FROM source_files").fetchall()
        finally:
            connection.close()
        known_paths = {str(Path(r[0]).resolve()).casefold() for r in rows}
        known_hashes = {r[1] for r in rows}
        result = ImportPreview(ignored=scan.ignored)
        for index, path in enumerate(scan.paths, 1):
            if cancel and cancel.is_set():
                raise ImportCancelled("Import cancelled before any pages were registered.")
            progress(index, len(scan.paths), f"Validating {path.name}")
            try:
                before = path.stat()
                metadata = self.loader.metadata(path)
                digest = sha256(path)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise OSError("Source changed during validation")
                metadata.update(original_filename=path.name, size_bytes=after.st_size,
                                mtime_ns=after.st_mtime_ns,
                                relative_path=str(path.relative_to(scan.root)) if scan.root else path.name)
                duplicate = str(path).casefold() in known_paths or digest in known_hashes
                result.candidates.append(Candidate(path, metadata, digest, duplicate))
                known_paths.add(str(path).casefold())
                known_hashes.add(digest)
            except Exception as exc:
                logging.exception("Image preflight failed: %s", path)
                result.errors.append(f"{path}: {exc}")
        return result

    def commit(self, preview: ImportPreview, import_duplicates: bool = False,
               progress: Progress = lambda *a: None, cancel: Event | None = None) -> int:
        candidates = [c for c in preview.candidates if import_duplicates or not c.duplicate]
        if not candidates:
            return 0
        connection = connect(self.project / "project.sqlite3")
        session = self.project / "sources" / ".imports" / str(uuid.uuid4())
        entries: list[dict] = []
        committed = False
        try:
            project = connection.execute("SELECT * FROM projects").fetchone()
            session.mkdir(parents=True)
            for candidate in candidates:
                source_id = str(uuid.uuid4())
                entries.append({"id": source_id, "filename": source_id + candidate.path.suffix.lower()})
            # A crash before DB commit leaves only disposable files listed in this journal.
            (session / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
            for index, (candidate, entry) in enumerate(zip(candidates, entries), 1):
                if cancel and cancel.is_set():
                    raise ImportCancelled("Import cancelled; no pages registered.")
                progress(index, len(candidates), f"Preparing {candidate.path.name}")
                stat = candidate.path.stat()
                if (stat.st_size, stat.st_mtime_ns) != (candidate.metadata["size_bytes"], candidate.metadata["mtime_ns"]):
                    raise OSError(f"Source changed after preview: {candidate.path}")
                check_path = candidate.path
                if project["source_mode"] == "copy":
                    check_path = session / entry["filename"]
                    shutil.copyfile(candidate.path, check_path)
                if sha256(check_path) != candidate.digest:
                    raise OSError(f"Source contents changed: {candidate.path}")
            if cancel and cancel.is_set():
                raise ImportCancelled("Import cancelled; no pages registered.")
            connection.execute("BEGIN IMMEDIATE")
            # Re-read the allocator inside the write transaction.
            number = connection.execute("SELECT next_page_number FROM projects").fetchone()[0]
            order = connection.execute("SELECT COALESCE(MAX(display_order),0) FROM pages").fetchone()[0]
            for offset, (candidate, entry) in enumerate(zip(candidates, entries)):
                stored = None
                if project["source_mode"] == "copy":
                    stored = f"sources/{entry['filename']}"
                    (session / entry["filename"]).replace(self.project / stored)
                connection.execute("INSERT INTO source_files(id,project_id,kind,original_path,stored_path,sha256,size_bytes,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
                                   (entry["id"], project["id"], "image", str(candidate.path), stored,
                                    candidate.digest, candidate.metadata["size_bytes"], json.dumps(candidate.metadata, ensure_ascii=False)))
                connection.execute("INSERT INTO pages(id,project_id,page_uid,display_order,source_file_id,label,width,height,status) VALUES(?,?,?,?,?,?,?,?,?)",
                                   (str(uuid.uuid4()), project["id"], f"P{number+offset:04d}", order+offset+1,
                                    entry["id"], f"第 {order+offset+1} 页", candidate.metadata["width"], candidate.metadata["height"], "ready"))
            connection.execute("UPDATE projects SET next_page_number=?", (number+len(candidates),))
            connection.commit()
            committed = True
            return len(candidates)
        finally:
            if not committed:
                connection.rollback()
            connection.close()
            if session.exists():
                try:
                    self.recover_session(session)
                except Exception:
                    logging.exception("Import journal cleanup deferred until project reopen: %s", session)

    def recover_session(self, session: Path) -> None:
        """Delete only journal-owned unregistered files; keep committed source files."""
        root = (self.project / "sources").resolve()
        if session.resolve().parent != root / ".imports":
            raise ValueError("Invalid import session path")
        manifest = session / "manifest.json"
        if not manifest.exists():
            return
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        connection = connect(self.project / "project.sqlite3")
        try:
            for entry in entries:
                filename = entry["filename"]
                if Path(filename).name != filename:
                    raise ValueError("Invalid recovery filename")
                registered = connection.execute("SELECT 1 FROM source_files WHERE id=?", (entry["id"],)).fetchone()
                if not registered:
                    (root / filename).unlink(missing_ok=True)
                (session / filename).unlink(missing_ok=True)
            manifest.unlink()
            session.rmdir()
        finally:
            connection.close()

    def recover(self) -> None:
        sessions = self.project / "sources" / ".imports"
        if sessions.is_dir():
            for session in sessions.iterdir():
                if session.is_dir():
                    self.recover_session(session)
