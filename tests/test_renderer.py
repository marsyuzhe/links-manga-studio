import hashlib

from PySide6.QtGui import QImage

from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.pages.page_service import PageService
from app.rendering.edits import RenderEditService
from app.rendering.renderer import PageRenderer, fit_font, wrapped_lines
from conftest import make_image
from test_ocr import FakeBackend


def test_render_nondestructive_fill_and_typeset(qapp, project_factory, tmp_path):
    project = project_factory()
    source = make_image(tmp_path / "page.png", 300, 200)
    initial_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([source])))
    page = PageService(project.connection, project.path).list_pages()[0]
    OCRPipeline(project.connection, project.path, FakeBackend()).process_page(page)
    block = TextBlockService(project.connection).for_page(page["id"])[0]
    edits = RenderEditService(project.connection, project.path)
    edits.set_erase(block["id"], "fill")
    edits.set_style(block["id"], {"font": "Arial", "max_size": 30, "color": "#000000"})
    TextBlockService(project.connection).save_translation(block["id"], "你好！")
    rendered = PageRenderer(project.connection, project.path).render_page(page)
    assert (rendered.width(), rendered.height()) == (300, 200)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == initial_hash
    assert rendered.pixelColor(25, 25).name() == "#ffffff"
    mask = QImage(300, 200, QImage.Format.Format_Grayscale8)
    mask.fill(0)
    assert edits.set_mask(block["id"], mask).is_file()
    assert PageRenderer(project.connection, project.path).render_page(page).width() == 300


def test_chinese_wrap_avoids_punctuation_start(qapp):
    font, lines = fit_font("你好，世界！欢迎。", "Arial", 70, 300, 12, 12)
    assert all(not line.startswith(("，", "。", "！")) for line in lines)
