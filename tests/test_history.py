from app.history import HistoryService
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.pages.page_service import PageService
from app.rendering.edits import RenderEditService
from PySide6.QtGui import QImage
from conftest import make_image
from test_ocr import FakeBackend


def test_undo_redo_review_translation_erase_and_style(project_factory, tmp_path):
    project = project_factory()
    source = make_image(tmp_path / "page.png", 300, 200)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([source])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    review = TextBlockService(project.connection)
    block = review.for_page(page["id"])[0]
    history = HistoryService(project.connection)
    review.update_review(block["id"], "corrected", 2)
    review.save_translation(block["id"], "译文")
    edits = RenderEditService(project.connection, project.path)
    edits.set_erase(block["id"], "fill")
    edits.set_style(block["id"], {"font": "Arial", "max_size": 20})
    assert history.undo()  # style link
    assert review.for_page(page["id"])[0]["style_id"] is None
    assert history.undo()  # style row
    assert project.connection.execute("SELECT COUNT(*) FROM styles").fetchone()[0] == 0
    assert history.undo()  # erase
    assert review.for_page(page["id"])[0]["erase_data_json"] == "{}"
    assert history.undo()  # translation insertion
    assert review.translation(block["id"]) is None
    assert history.undo()  # review
    assert review.for_page(page["id"])[0]["source_text"] == "HELLO"
    assert not history.undo()
    for _ in range(5):
        assert history.redo()
    assert review.translation(block["id"])["text"] == "译文"
    assert review.for_page(page["id"])[0]["style_id"] is not None


def test_mask_file_undo_redo(project_factory, tmp_path):
    project = project_factory()
    source = make_image(tmp_path / "page.png", 100, 100)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([source])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    block = TextBlockService(project.connection).for_page(page["id"])[0]
    mask = QImage(100, 100, QImage.Format.Format_Grayscale8)
    mask.fill(255)
    target = RenderEditService(project.connection, project.path).set_mask(block["id"], mask)
    assert target.is_file()
    history = HistoryService(project.connection)
    assert history.undo()  # link
    assert history.undo()  # file
    assert not target.exists()
    assert history.redo()
    assert target.exists()
    assert history.redo()
    assert TextBlockService(project.connection).for_page(page["id"])[0]["mask_path"]
