from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.pages.page_service import PageService
from conftest import make_image
from test_ocr import FakeBackend
from app.ui.window import MainWindow
from app.history import HistoryService


def test_review_and_translation_survive_reopen(project_factory, tmp_path):
    project = project_factory()
    image = make_image(tmp_path / "page.png", 300, 200)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([image])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    review = TextBlockService(project.connection)
    block = review.for_page(page["id"])[0]
    review.update_review(block["id"], "HELLO!", 2, "speech")
    review.save_translation(block["id"], "你好！", "人工翻译")
    project_path = project.path
    project.close_project()
    project.open_project(project_path)
    review = TextBlockService(project.connection)
    restored = review.for_page(page["id"])[0]
    assert restored["source_text"] == "HELLO!" and restored["reading_order"] == 2
    assert review.translation(block["id"])["text"] == "你好！"


def test_offscreen_ocr_review_editor(qtbot, project_factory, tmp_path):
    project = project_factory()
    image = make_image(tmp_path / "page.png", 300, 200)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([image])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    block = TextBlockService(project.connection).for_page(page["id"])[0]
    window = MainWindow(project, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    qtbot.waitUntil(lambda: window.workspace.canvas.page_id == page["id"], timeout=10000)
    window.workspace.canvas.block_selected.emit(block["id"])
    assert window.workspace.block_editor.isVisible()
    window.workspace.block_translation.setPlainText("你好")
    window.workspace.save_block()
    assert TextBlockService(project.connection).translation(block["id"])["text"] == "你好"
    window.close()


def test_geometry_duplicate_delete_and_undo(project_factory, tmp_path):
    project = project_factory()
    source = make_image(tmp_path / "page.png", 300, 200)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([source])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    review = TextBlockService(project.connection)
    first = review.for_page(page["id"])[0]
    review.update_geometry(first["id"], [30, 25, 130, 75], 15)
    copy_id = review.duplicate(first["id"])
    assert [row["text_uid"] for row in review.for_page(page["id"])] == ["P0001-T001", "P0001-T002"]
    review.delete(copy_id)
    assert len(review.for_page(page["id"])) == 1
    assert HistoryService(project.connection).undo()
    assert len(review.for_page(page["id"])) == 2
