from PySide6.QtCore import QPoint, Qt
from conftest import make_image
from app.importers.folder_importer import scan_folder
from app.importers.image_importer import ImageImporter
from app.ui.window import MainWindow


def test_canvas_navigation_race_pan_and_missing(qtbot, project_factory, tmp_path):
    service = project_factory(mode="reference")
    source = tmp_path / "原图"
    for i in range(1, 101):
        make_image(source / f"第{i}页.png", 300, 450, i)
    importer = ImageImporter(service.path)
    importer.commit(importer.validate(scan_folder(source)))
    window = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    ws = window.workspace
    qtbot.waitUntil(lambda: not ws.jobs, timeout=10000)
    qtbot.waitUntil(lambda: ws.canvas.page_id == ws.current_id, timeout=10000)
    assert not ws.actions["previous"].isEnabled()
    for row in range(1, 50):
        ws.panel.setCurrentIndex(ws.model.index(row))
    last_id = ws.model.pages[49]["id"]
    qtbot.waitUntil(lambda: ws.canvas.page_id == last_id, timeout=10000)
    qtbot.wait(100)
    assert ws.canvas.page_id == last_id
    assert ws.image_worker.pending_count <= 3
    ws.actions["next"].trigger()
    assert ws.current_row == 50
    ws.actions["previous"].trigger()
    assert ws.current_row == 49
    ws.actions["actual"].trigger()
    qtbot.waitUntil(lambda: ws.canvas.page_id == last_id, timeout=10000)
    ws.canvas.set_zoom(4)
    canvas = ws.canvas
    start = canvas.horizontalScrollBar().value()
    qtbot.mousePress(canvas.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(150, 150))
    qtbot.mouseMove(canvas.viewport(), QPoint(210, 150))
    qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(210, 150))
    assert canvas.horizontalScrollBar().value() != start
    canvas.set_zoom(100)
    assert canvas.transform().m11() == 16
    canvas.set_zoom(.001)
    assert canvas.transform().m11() == .05
    ws.panel.setCurrentIndex(ws.model.index(99))
    assert not ws.actions["next"].isEnabled()
    (source / "第1页.png").unlink()
    ws.panel.setCurrentIndex(ws.model.index(0))
    qtbot.waitUntil(lambda: ws.model.pages[0]["status"] == "missing", timeout=10000)
    (source / "第2页.png").write_bytes(b"broken")
    ws.panel.setCurrentIndex(ws.model.index(1))
    qtbot.waitUntil(lambda: ws.model.pages[1]["status"] == "broken", timeout=10000)
    ws.panel.setCurrentIndex(ws.model.index(2))
    qtbot.waitUntil(lambda: ws.canvas.page_id == ws.model.pages[2]["id"], timeout=10000)
    assert len(ws.model.pixmaps) <= 64
    assert len(list((service.path / "cache/thumbnails").glob("*.png"))) < 100
    window.close()
