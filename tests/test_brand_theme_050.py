"""0.5.0 identity, theme persistence and legacy project compatibility."""
import json
from PySide6.QtWidgets import QLabel

from app import __version__
from app.branding import DISPLAY_NAME, AUTHOR_EN
from app.config import Config
from app.project import ProjectService
from app.themes.manager import ThemeManager
from app.ui.about_dialog import AboutDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.window import MainWindow


def test_brand_about_and_legacy_config(qtbot, tmp_path):
    assert __version__ == "0.6.0"
    assert (DISPLAY_NAME, AUTHOR_EN) == ("Links Manga Studio", "Links Tam")
    config = Config(tmp_path / "LinksMangaWorkspace" / "config.json")
    window = MainWindow(ProjectService(config), tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    assert DISPLAY_NAME in window.windowTitle()
    about = AboutDialog(window)
    qtbot.addWidget(about)
    assert "0.6.0" in about.version_label.text()
    assert "Created by Links Tam" in " ".join(label.text() for label in about.findChildren(QLabel))
    assert window.author_footer.text() == "Created by Links Tam"
    project = window.service.create_project(tmp_path, "Legacy Compatible")
    window.service.close_project()
    window.service.open_project(project)
    before = json.loads((project / "project.json").read_text(encoding="utf-8"))
    window.set_theme("light")
    assert json.loads((project / "project.json").read_text(encoding="utf-8")) == before
    assert config.data["theme"] == "light"
    assert config.path.parent.name == "LinksMangaWorkspace"
    window.service.close_project()


def test_dark_light_system_and_settings_runtime_language(qtbot, tmp_path, monkeypatch):
    config = Config(tmp_path / "config.json")
    window = MainWindow(ProjectService(config), tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    for mode, effective in (("dark", "dark"), ("light", "light")):
        window.set_theme(mode)
        assert window.theme.effective == effective
        assert window.workspace.canvas.tokens == window.theme.tokens
        assert ThemeManager(Config(config.path)).mode == mode
    monkeypatch.setattr("app.themes.manager.system_is_light", lambda: True)
    window.set_theme("system")
    assert window.theme.effective == "light"
    dialog = SettingsDialog(window)
    qtbot.addWidget(dialog)
    window.language.set_language("en_US")
    assert dialog.windowTitle() == "Settings"
    assert dialog.navigation.item(1).text() == "Appearance"
    window.language.set_language("zh_CN")
    assert dialog.navigation.item(1).text() == "外观"
