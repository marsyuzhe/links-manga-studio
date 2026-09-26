"""Register PDF page metadata in one transaction without rasterizing pages."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from threading import Event

import pypdfium2 as pdfium

from app.database.database import connect
from app.importers.image_importer import sha256


class PdfImporter:
    def __init__(self, project: Path) -> None:
        self.project = project

    def import_file(self, source: Path, progress=lambda *a: None, cancel: Event | None = None) -> int:
        source = source.resolve()
        stat = source.stat()
        digest = sha256(source)
        document = pdfium.PdfDocument(source)
        try:
            dimensions = []
            count = len(document)
            for index in range(count):
                if cancel and cancel.is_set():
                    raise RuntimeError("PDF import cancelled")
                width, height = document.get_page_size(index)
                dimensions.append((round(width), round(height)))
                if index % 50 == 0 or index + 1 == count:
                    progress(index + 1, count, f"Reading PDF page {index + 1}")
        finally:
            document.close()
        if not count:
            raise ValueError("PDF contains no pages")
        if (source.stat().st_size, source.stat().st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise OSError("PDF changed during metadata scan")
        connection = connect(self.project / "project.sqlite3")
        copied: Path | None = None
        try:
            project = connection.execute("SELECT * FROM projects").fetchone()
            existing = connection.execute("SELECT 1 FROM source_files WHERE sha256=? AND kind='pdf'", (digest,)).fetchone()
            if existing:
                raise ValueError("This PDF has already been imported")
            source_id = str(uuid.uuid4())
            stored = None
            if project["source_mode"] == "copy":
                stored = f"sources/{source_id}.pdf"
                copied = self.project / stored
                temporary = copied.with_suffix(".pdf.tmp")
                try:
                    shutil.copyfile(source, temporary)
                    if sha256(temporary) != digest:
                        raise OSError("PDF changed while copying")
                    temporary.replace(copied)
                finally:
                    temporary.unlink(missing_ok=True)
            if cancel and cancel.is_set():
                raise RuntimeError("PDF import cancelled")
            connection.execute("BEGIN IMMEDIATE")
            next_number = project["next_page_number"]
            order = connection.execute("SELECT COALESCE(MAX(display_order),0) FROM pages").fetchone()[0]
            metadata = {"original_filename": source.name, "mtime_ns": stat.st_mtime_ns,
                        "pdf_engine": "PDFium", "page_coordinate_space": "pdf-page-72dpi-v1"}
            connection.execute("""INSERT INTO source_files
                (id,project_id,kind,original_path,stored_path,sha256,size_bytes,page_count,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?)""", (source_id, project["id"], "pdf", str(source), stored,
                                             digest, stat.st_size, count, json.dumps(metadata, ensure_ascii=False)))
            for index, (width, height) in enumerate(dimensions):
                connection.execute("""INSERT INTO pages
                    (id,project_id,page_uid,display_order,source_file_id,source_page_index,label,width,height,status)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""", (str(uuid.uuid4()), project["id"],
                    f"P{next_number + index:04d}", order + index + 1, source_id, index,
                    f"第 {order + index + 1} 页", width, height, "ready"))
            connection.execute("UPDATE projects SET next_page_number=?", (next_number + count,))
            connection.commit()
            return count
        except Exception:
            connection.rollback()
            if copied:
                copied.unlink(missing_ok=True)
            raise
        finally:
            connection.close()
