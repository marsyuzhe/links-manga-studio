import pytest
from conftest import make_image
from app.importers.folder_importer import scan_folder
from app.importers.image_importer import ImageImporter
from app.pages.page_service import PageService


def test_order_labels_uid_reopen_and_relocate(project_factory, tmp_path):
    service = project_factory(mode="reference")
    root = tmp_path / "原目录"
    for i in range(1, 6):
        make_image(root / f"第{i}页.png", seed=i)
    importer = ImageImporter(service.path)
    importer.commit(importer.validate(scan_folder(root)))
    pages_service = PageService(service.connection, service.path)
    original = pages_service.list_pages()
    pages_service.move(original[0]["id"], 1)
    pages_service.set_label(original[0]["id"], "封面")
    project_path = service.path
    service.close_project()
    service.open_project(project_path)
    pages_service = PageService(service.connection, service.path)
    pages = pages_service.list_pages()
    assert pages[1]["page_uid"] == "P0001" and pages[1]["label"] == "封面"
    assert pages[1]["display_order"] == 2
    destination = tmp_path / "移动后目录"
    root.rename(destination)
    assert all(p["status"] == "missing" for p in pages_service.health_check())
    report = pages_service.relocate(destination)
    assert report == {"relocated": 5, "unresolved": []}
    assert all(p["status"] == "ready" for p in pages_service.list_pages())


def test_relocate_rejects_wrong_content(project_factory, tmp_path):
    service = project_factory(mode="reference")
    root = tmp_path / "original"
    make_image(root / "1.bmp", seed=1)
    importer = ImageImporter(service.path)
    importer.commit(importer.validate(scan_folder(root)))
    root.rename(tmp_path / "moved")
    new_root = tmp_path / "wrong"
    make_image(new_root / "1.bmp", seed=2)  # same size, different hash
    report = PageService(service.connection, service.path).relocate(new_root)
    assert report["relocated"] == 0 and len(report["unresolved"]) == 1
