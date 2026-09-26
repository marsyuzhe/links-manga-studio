from pathlib import Path

import pypdfium2 as pdfium
import pytest

from app.pages.page_service import PageService
from app.pdf.importer import PdfImporter
from app.pdf.render import PdfRenderService, page_to_render, render_to_page
from app.ui.window import MainWindow


def make_pdf(path: Path, count: int = 1000) -> Path:
    with pdfium.PdfDocument.new() as document:
        for _ in range(count):
            document.new_page(width=240, height=360).close()
        document.save(path)
    return path


@pytest.mark.parametrize("mode", ["copy", "reference"])
def test_thousand_page_metadata_and_lazy_cache(project_factory, tmp_path, mode):
    service = project_factory(name=f"PDF测试{mode}", mode=mode)
    source = make_pdf(tmp_path / "千页.pdf")
    assert PdfImporter(service.path).import_file(source) == 1000
    pages = PageService(service.connection, service.path).list_pages()
    assert len(pages) == 1000
    assert pages[0]["page_uid"] == "P0001"
    assert pages[-1]["page_uid"] == "P1000"
    assert pages[-1]["source_page_index"] == 999
    assert pages[0]["source_kind"] == "pdf"
    renderer = PdfRenderService(service.path)
    assert not list(renderer.root.rglob("*.png"))
    image = renderer.render(pages[499])
    assert image.width() > 240 and image.height() > 360
    assert len(list(renderer.root.rglob("*.png"))) == 1
    assert renderer.render(pages[499], 300, "ocr").height() > image.height()
    assert len(list(renderer.root.rglob("*.png"))) == 2
    assert renderer.cache_path(pages[499], 110, "preview") != renderer.cache_path(pages[499], 300, "ocr")
    with pytest.raises(ValueError, match="already"):
        PdfImporter(service.path).import_file(source)
    assert len(PageService(service.connection, service.path).list_pages()) == 1000
    if mode == "copy":
        source.unlink()
        assert not renderer.render(pages[20]).isNull()
    else:
        source.unlink()
        with pytest.raises(FileNotFoundError, match="Missing Source"):
            renderer.render(pages[20])


def test_pdf_page_coordinate_round_trip():
    for dpi in (24, 110, 250, 300):
        pixels = round(240 * dpi / 72)
        assert render_to_page(page_to_render(73.2, 240, pixels), 240, pixels) == pytest.approx(73.2)


def test_pdf_workspace_async_navigation(qtbot, project_factory, tmp_path):
    service = project_factory(mode="reference")
    assert PdfImporter(service.path).import_file(make_pdf(tmp_path / "漫画.pdf", 60)) == 60
    window = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    workspace = window.workspace
    qtbot.waitUntil(lambda: not workspace.jobs, timeout=10000)
    assert workspace.actions["pdf"].isEnabled()
    for row in range(1, 50):
        workspace.panel.setCurrentIndex(workspace.model.index(row))
    last_id = workspace.model.pages[49]["id"]
    qtbot.waitUntil(lambda: workspace.canvas.page_id == last_id, timeout=10000)
    qtbot.wait(100)
    assert workspace.canvas.page_id == last_id
    assert workspace.model.pages[49]["source_page_index"] == 49
    assert "漫画.pdf" in workspace.inspector.text()
    assert not list((service.path / "cache/pdf_render/ocr").glob("*.png"))
    window.close()
