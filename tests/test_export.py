from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.pages.page_service import PageService
from app.rendering.export import export_pages
from conftest import make_image


def test_export_formats_and_single_failure_recovery(project_factory, tmp_path):
    project = project_factory(mode="reference")
    sources = [make_image(tmp_path / f"p{i}.png", 128, 192, i) for i in range(3)]
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files(sources)))
    pages = PageService(project.connection, project.path).list_pages()
    sources[1].rename(tmp_path / "moved.png")
    result = export_pages(project.path, [p["id"] for p in pages])
    assert result["status"] == "failed" and result["completed"] == 2
    assert len(list((project.path / "exports").rglob("*.png"))) == 2
    (tmp_path / "moved.png").rename(sources[1])
    resumed = export_pages(project.path, task_id=result["task_id"])
    assert resumed["status"] == "completed" and resumed["completed"] == 3
    assert len(list((project.path / "exports").rglob("*.png"))) == 3
    assert export_pages(project.path, [pages[0]["id"]], "jpg")["status"] == "completed"
    assert export_pages(project.path, [pages[0]["id"]], "webp")["status"] == "completed"
