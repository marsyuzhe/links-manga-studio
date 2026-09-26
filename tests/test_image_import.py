import json
import shutil
from threading import Event
import pytest
from conftest import make_image
from app.importers.folder_importer import scan_files, scan_folder
from app.importers.image_importer import ImageImporter, ImportCancelled
from app.pages.page_service import PageService


@pytest.mark.parametrize("mode", ["copy", "reference"])
def test_import_five_unicode_all_formats(project_factory, tmp_path, mode):
    service = project_factory(mode=mode)
    root = tmp_path / "漫画素材"
    files = [make_image(root / f"第{i:03d}页.{ext}", seed=i) for i, ext in enumerate(["JPG", "jpeg", "png", "webp", "bmp"], 1)]
    importer = ImageImporter(service.path)
    preview = importer.validate(scan_files(files))
    assert len(preview.candidates) == 5 and not preview.errors
    assert PageService(service.connection, service.path).list_pages() == []
    assert importer.commit(preview) == 5
    pages = PageService(service.connection, service.path).list_pages()
    assert [p["page_uid"] for p in pages] == [f"P{i:04d}" for i in range(1, 6)]
    assert all(p["metadata"]["original_filename"].startswith("第") for p in pages)
    assert all(bool(p["stored_path"]) == (mode == "copy") for p in pages)
    again = importer.validate(scan_folder(root))
    assert again.duplicates == 5
    assert importer.commit(again) == 0
    assert importer.commit(again, import_duplicates=True) == 5
    assert len(PageService(service.connection, service.path).list_pages()) == 10


def test_broken_preflight_and_failure_atomicity(project_factory, tmp_path, monkeypatch):
    service = project_factory()
    root = tmp_path / "input"
    make_image(root / "1.png", seed=1)
    make_image(root / "2.png", seed=2)
    (root / "broken.jpg").write_bytes(b"not a JPEG")
    importer = ImageImporter(service.path)
    preview = importer.validate(scan_folder(root))
    assert len(preview.errors) == 1 and len(preview.candidates) == 2
    copy = shutil.copyfile
    calls = []
    def failing_copy(source, destination):
        calls.append(source)
        if len(calls) == 2:
            raise PermissionError("controlled copy failure")
        return copy(source, destination)
    monkeypatch.setattr(shutil, "copyfile", failing_copy)
    with pytest.raises(PermissionError):
        importer.commit(preview)
    assert service.connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
    assert not list((service.path / "sources").glob("*.png"))
    monkeypatch.setattr(shutil, "copyfile", copy)
    assert importer.commit(preview) == 2


def test_cancel_and_changed_source(project_factory, tmp_path):
    service = project_factory()
    path = make_image(tmp_path / "a.png")
    importer = ImageImporter(service.path)
    preview = importer.validate(scan_files([path]))
    cancel = Event()
    cancel.set()
    with pytest.raises(ImportCancelled):
        importer.commit(preview, cancel=cancel)
    path.write_bytes(b"changed")
    with pytest.raises(OSError, match="Source changed"):
        importer.commit(preview)
    assert service.connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0


def test_recover_interrupted_import(project_factory):
    service = project_factory()
    session = service.path / "sources" / ".imports" / "interrupted"
    session.mkdir(parents=True)
    source = service.path / "sources" / "owned.png"
    source.write_bytes(b"uncommitted")
    (session / "manifest.json").write_text(json.dumps([{"id": "unregistered", "filename": "owned.png"}]))
    ImageImporter(service.path).recover()
    assert not source.exists() and not session.exists()


def test_unreadable_source_report(project_factory, tmp_path, monkeypatch):
    service = project_factory()
    path = make_image(tmp_path / "denied.png")
    importer = ImageImporter(service.path)
    def denied(path):
        raise PermissionError("Access denied")
    monkeypatch.setattr(importer.loader, "metadata", denied)
    result = importer.validate(scan_files([path]))
    assert not result.candidates and "Access denied" in result.errors[0]
