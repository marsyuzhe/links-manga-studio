"""Capture deterministic Qt offscreen UI snapshots for visual review."""
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from app.config import Config
from app.project import ProjectService
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.pages.page_service import PageService
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.workflow import WorkflowService
from app.quality.checker import QualityChecker
from app.ui.window import MainWindow
from app.ui.font_picker import FontPicker


class SampleOCR:
    name = "Snapshot Fixture"
    model = "fixture"

    def recognize(self, image):
        return [{"polygon": [[155, 135], [455, 135], [455, 235], [155, 235]],
                 "text": "こんにちは、世界。", "confidence": .94}]


def sample_page(path: Path) -> None:
    image = QImage(650, 920, QImage.Format.Format_RGB32)
    image.fill(QColor("#F8F6F1"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#303744"), 3))
    painter.drawRect(35, 38, 580, 835)
    painter.drawLine(35, 475, 615, 475)
    painter.setPen(QPen(QColor("#303744"), 2))
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawEllipse(115, 105, 400, 175)
    painter.setFont(QFont("Microsoft YaHei", 22))
    painter.drawText(155, 178, "こんにちは、世界。")
    painter.setBrush(QColor("#DDE3EB"))
    painter.drawEllipse(155, 525, 355, 245)
    painter.setFont(QFont("Segoe UI", 14))
    painter.drawText(250, 655, "MANGA PAGE")
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError("Cannot save snapshot fixture")


def spin(app, predicate, timeout=15):
    until = time.monotonic() + timeout
    while not predicate() and time.monotonic() < until:
        app.processEvents()
        time.sleep(.02)
    if not predicate():
        raise TimeoutError("UI did not reach snapshot state")
    app.processEvents()


def capture(widget, path):
    widget.repaint()
    QApplication.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"Could not capture {path}")


def main():
    app = QApplication([])
    output = Path(__file__).resolve().parents[1] / "docs" / "ui_snapshots" / "0.5.0"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lmw-ui-") as temporary:
        folder = Path(temporary)
        config = Config(folder / "config.json")
        service = ProjectService(config)
        window = MainWindow(service, folder / "app.log")
        window.resize(1366, 768)
        window.show()
        spin(app, lambda: window.isVisible())
        capture(window, output / "startup_dark.png")
        window.set_theme("light")
        capture(window, output / "startup_light.png")
        window.set_theme("dark")
        service.create_project(folder, "视觉验收", "copy")
        source = folder / "第001页.png"
        sample_page(source)
        importer = ImageImporter(service.path)
        importer.commit(importer.validate(scan_files([source])))
        page = PageService(service.connection, service.path).list_pages()[0]
        OCRPipeline(service.connection, service.path, SampleOCR()).process_page(page)
        block = TextBlockService(service.connection).for_page(page["id"])[0]
        WorkflowService(service.connection, service.path).erase_and_refill(block["id"], "你好，世界。")
        window._project_opened()
        spin(app, lambda: window.workspace.canvas.page_id == page["id"] and not window.workspace.jobs)
        capture(window, output / "workspace_dark.png")
        window.workspace.select_block(block["id"])
        capture(window, output / "inspector_translation.png")
        window.set_theme("light")
        capture(window, output / "workspace_light.png")
        window.set_theme("dark")
        window.resize(1920, 1080)
        spin(app, lambda: window.width() == 1920)
        capture(window, output / "workspace-1920.png")
        from app.ui.settings_dialog import SettingsDialog
        settings = SettingsDialog(window)
        settings.navigation.setCurrentRow(1)
        settings.show()
        spin(app, lambda: settings.isVisible())
        capture(settings, output / "settings_appearance.png")
        settings.close()
        from app.ui.about_dialog import AboutDialog
        about = AboutDialog(window)
        about.show()
        spin(app, lambda: about.isVisible())
        capture(about, output / "about.png")
        about.close()
        picker = FontPicker([{"family": "Microsoft YaHei", "supported_languages": ["zh"]},
                             {"family": "Arial", "supported_languages": []}], "Microsoft YaHei",
                            window, config=config, language=window.language, sample="你好，世界。")
        picker.show()
        spin(app, lambda: picker.isVisible())
        capture(picker, output / "font_browser.png")
        picker.close()
        report = QualityChecker(service.connection).scan()
        window.workspace._show_quality_report(report)
        capture(window, output / "quality_check.png")
        window.close_project()
        window.resize(1366, 768)
        capture(window, output / "startup-recent.png")
        window.close()
    print(output)


if __name__ == "__main__":
    main()
