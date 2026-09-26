"""Workflow acceptance tests for direct import, erasure and in-place refill."""
import json
import sqlite3
from PySide6.QtCore import QPoint, QPointF, Qt, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import Config
from app.project import ProjectService
from app.ui.window import MainWindow
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.pages.page_service import PageService
from app.rendering.renderer import PageRenderer
from app.workflow import WorkflowService
from app.history import HistoryService
from app.database.schema import VERSION
from conftest import make_image
from test_ocr import FakeBackend
from test_pdf import make_pdf


def prepare_block(project_factory, tmp_path):
    project = project_factory()
    source = make_image(tmp_path / "page.png", 300, 200)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([source])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    block = TextBlockService(project.connection).for_page(page["id"])[0]
    return project, page, block


def test_drop_pdf_creates_and_opens_project(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    pdf = make_pdf(tmp_path / "第001话.pdf", 2)
    service = ProjectService(Config(tmp_path / "config.json"))
    window = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    enter = QDragEnterEvent(QPoint(50, 50), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(window, enter)
    assert enter.isAccepted()
    event = QDropEvent(QPointF(50, 50), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(window, event)
    qtbot.waitUntil(lambda: service.path is not None and not window.workspace.jobs, timeout=10000)
    assert service.path.name == "第001话.lmw"
    assert len(PageService(service.connection, service.path).list_pages()) == 2
    window.close()


def test_export_original_text(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    output = tmp_path / "原文.tsv"
    assert WorkflowService(project.connection, project.path).export_source([page["id"]], output) == 1
    text = output.read_text(encoding="utf-8-sig")
    assert block["text_uid"] in text and "HELLO" in text and page["page_uid"] in text


def test_export_original_docx(project_factory, tmp_path):
    from docx import Document
    project, page, block = prepare_block(project_factory, tmp_path)
    output = tmp_path / "原文.docx"
    assert WorkflowService(project.connection, project.path).export_source_docx([page["id"]], output) == 1
    content = "\n".join(p.text for p in Document(output).paragraphs)
    assert block["text_uid"] in content and page["page_uid"] in content and "HELLO" in content


def test_ui_primary_erase_refill_and_undo(qtbot, project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    window = MainWindow(project, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    qtbot.waitUntil(lambda: not window.workspace.jobs and window.workspace.canvas.page_id == page["id"], timeout=10000)
    workspace = window.workspace
    assert workspace.right_tabs.tabText(0) == window.language.tr("panel.translation")
    workspace.select_block(block["id"])
    assert workspace.canvas.block_items[block["id"]].isSelected()
    workspace.focus_translation_editor(block["id"])
    assert workspace.right_tabs.currentIndex() == 0
    assert workspace.block_translation.hasFocus()
    workspace.block_translation.setPlainText("你好")
    workspace.erase_refill_button.click()
    review = TextBlockService(project.connection)
    assert review.for_page(page["id"])[0]["erase_status"] == "erased"
    assert review.translation(block["id"])["text"] == "你好"
    assert "erase" in workspace.actions["undo"].text().lower() or "擦除" in workspace.actions["undo"].text()
    workspace.undo()
    assert review.for_page(page["id"])[0]["erase_status"] == "none"
    assert review.translation(block["id"]) is None
    window.close()


def test_quick_erase_keeps_text_block(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    assert WorkflowService(project.connection, project.path).erase_blocks([block["id"]]) == 1
    current = TextBlockService(project.connection).for_page(page["id"])[0]
    assert current["id"] == block["id"]
    assert current["text_uid"] == block["text_uid"]
    assert current["erase_status"] == "erased"


def test_refill_translation_at_original_box(qapp, project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    workflow = WorkflowService(project.connection, project.path)
    workflow.erase_blocks([block["id"]])
    workflow.fill_translation(block["id"], "你好")
    assert TextBlockService(project.connection).translation(block["id"])["text"] == "你好"
    assert TextBlockService(project.connection).for_page(page["id"])[0]["typeset_status"] == "ready"
    rendered = PageRenderer(project.connection, project.path).render_page(page)
    assert not rendered.isNull()
    assert rendered.pixelColor(20, 20).name() == "#ffffff"


def test_erased_box_can_be_edited_again(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    workflow = WorkflowService(project.connection, project.path)
    workflow.erase_blocks([block["id"]])
    workflow.fill_translation(block["id"], "初稿")
    workflow.fill_translation(block["id"], "修订稿")
    review = TextBlockService(project.connection)
    assert review.translation(block["id"])["text"] == "修订稿"
    assert review.for_page(page["id"])[0]["text_uid"] == block["text_uid"]
    assert HistoryService(project.connection).undo()
    assert review.translation(block["id"])["text"] == "初稿"
    assert review.for_page(page["id"])[0]["typeset_status"] == "ready"


def test_v2_project_migrates_workflow_fields(project_factory):
    service = project_factory()
    path = service.path
    service.close_project()
    with sqlite3.connect(path / "project.sqlite3") as db:
        for column in ("erase_status", "typeset_status", "text_style"):
            db.execute(f"ALTER TABLE text_blocks DROP COLUMN {column}")
        db.execute("UPDATE projects SET schema_version=2")
        db.execute("PRAGMA user_version=2")
    metadata_path = path / "project.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema_version"] = 2
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    service.open_project(path)
    columns = {row[1] for row in service.connection.execute("PRAGMA table_info(text_blocks)")}
    assert {"erase_status", "typeset_status", "text_style"} <= columns
    assert service.connection.execute("PRAGMA user_version").fetchone()[0] == VERSION
    assert len(list((path / "backups").glob("before-schema-v3-*.sqlite3"))) == 1


def test_erase_and_refill_is_one_undoable_command(qapp, project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    workflow = WorkflowService(project.connection, project.path)
    review = TextBlockService(project.connection)
    before = PageRenderer(project.connection, project.path).render_page(page)
    workflow.erase_and_refill(block["id"], "中文译文")
    updated = review.for_page(page["id"])[0]
    assert updated["text_uid"] == block["text_uid"]
    assert updated["source_text"] == block["source_text"]
    assert updated["erase_status"] == "erased" and updated["typeset_status"] == "ready"
    assert review.translation(block["id"])["text"] == "中文译文"
    rendered = PageRenderer(project.connection, project.path).render_page(page)
    assert not rendered.isNull() and rendered != before
    history = HistoryService(project.connection)
    assert history.next_command() == "erase_and_refill"
    assert history.undo()
    assert review.for_page(page["id"])[0]["erase_status"] == "none"
    assert review.for_page(page["id"])[0]["typeset_status"] == "pending"
    assert review.translation(block["id"]) is None
    assert history.next_command(redo=True) == "erase_and_refill"
    assert history.redo()
    assert review.for_page(page["id"])[0]["erase_status"] == "erased"
    assert review.translation(block["id"])["text"] == "中文译文"


def test_blank_translation_does_not_erase(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    workflow = WorkflowService(project.connection, project.path)
    import pytest
    with pytest.raises(ValueError, match="translation"):
        workflow.erase_and_refill(block["id"], "  ")
    assert TextBlockService(project.connection).for_page(page["id"])[0]["erase_status"] == "none"
    assert HistoryService(project.connection).next_command() is None
