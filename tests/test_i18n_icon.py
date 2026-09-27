"""Language and icon acceptance checks for the single application UI."""
import json
import struct
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from conftest import make_image
from app.config import Config
from app.i18n import LanguageManager, default_language
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.main import configure_application_icon
from app.resources import resource_path
from app.ui.window import MainWindow


def test_default_language_and_catalog_coverage(tmp_path):
    assert default_language("zh-CN") == "zh_CN"
    assert default_language("zh_SG") == "zh_CN"
    assert default_language("ja-JP") == "en_US"
    assert default_language("en-US") == "en_US"
    language = LanguageManager(Config(tmp_path / "config.json"))
    assert set(language.catalogs["zh_CN"]) == set(language.catalogs["en_US"])


def test_switch_persist_fallback_and_data_preservation(tmp_path):
    path = tmp_path / "config.json"
    language = LanguageManager(Config(path))
    language.set_language("zh_CN")
    assert language.tr("action.new_project") == "新建项目"
    page = {"label": "第 5 页", "display_order": 5, "page_uid": "P0007"}
    assert language.display_label(page) == "第 5 页"
    language.set_language("en_US")
    assert language.tr("action.new_project") == "New Project"
    assert language.display_label(page) == "Page 5"
    assert page["label"] == "第 5 页" and page["page_uid"] == "P0007"
    assert language.tr("missing.translation.key") == "missing.translation.key"
    assert LanguageManager(Config(path)).language == "en_US"
    language.set_language("unknown")
    assert language.language == "en_US" and json.loads(path.read_text(encoding="utf-8"))["language"] == "en_US"


def test_live_window_switch_and_recreate(qtbot, project_factory, tmp_path):
    service = project_factory()
    window = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window.language.set_language("zh_CN")
    assert window.file_menu.title() == "文件"
    assert window.new_button.text() == "新建项目"
    assert window.workspace.actions["images"].text() == "导入图片"
    assert window.language_actions["zh_CN"].isChecked()
    window._project_opened()
    assert not window.workspace.progress_label.isVisible()
    assert window.workspace.panel.accessibleName() == "页面"
    assert "页面属性" in window.workspace.inspector.text()
    window.language.set_language("en_US")
    assert window.file_menu.title() == "File"
    assert window.workspace.actions["images"].text() == "Import Images"
    assert window.workspace.panel.accessibleName() == "Pages"
    assert "Page Information" in window.workspace.inspector.text()
    assert window.language_actions["en_US"].isChecked()
    window.language.set_language("zh_CN")
    assert window.file_menu.title() == "文件"
    window.close()
    second = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(second)
    assert second.file_menu.title() == "文件"
    second.close()


def test_real_multisize_ico_and_app_icon(qapp):
    icon_path = resource_path("assets/icons/app_icon.ico")
    assert icon_path.is_file()
    data = icon_path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, 7)
    sizes = [struct.unpack_from("<B", data, 6 + 16*i)[0] or 256 for i in range(count)]
    assert sizes == [16, 24, 32, 48, 64, 128, 256]
    assert all(resource_path(f"assets/icons/app_icon_{size}.png").is_file() for size in sizes)
    icon = QIcon(str(icon_path))
    assert not icon.isNull()
    configure_application_icon(qapp)
    assert not qapp.windowIcon().isNull()


def test_live_page_text_switch_keeps_project_records(qtbot, project_factory, tmp_path):
    service = project_factory(name="中文项目", mode="reference")
    source = make_image(tmp_path / "图片" / "第001页.png")
    importer = ImageImporter(service.path)
    assert importer.commit(importer.validate(scan_files([source]))) == 1
    window = MainWindow(service, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    qtbot.waitUntil(lambda: bool(not window.workspace.jobs and window.workspace.canvas.page_id), timeout=10000)
    window.language.set_language("zh_CN")
    assert "页面属性" in window.workspace.inspector.text()
    assert "第 1 / 1 页" in window.statusBar().currentMessage()
    window.language.set_language("en_US")
    assert "Page Information" in window.workspace.inspector.text()
    assert "Label: Page 1" in window.workspace.inspector.text()
    assert "Page 1 / 1" in window.statusBar().currentMessage()
    assert not window.workspace.model.data(window.workspace.model.index(0), Qt.ItemDataRole.ToolTipRole)
    assert "第001页.png" in window.workspace.inspector.text()
    row = service.connection.execute("SELECT page_uid,label FROM pages").fetchone()
    assert row["page_uid"] == "P0001" and row["label"] == "第 1 页"
    window.close()
