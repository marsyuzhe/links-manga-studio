"""Visual-shell behavior checks; core workflow remains covered elsewhere."""
from PySide6.QtCore import Qt

from app.config import Config
from app.project import ProjectService
from app.ui.window import MainWindow


def make_window(qtbot, tmp_path):
    window = MainWindow(ProjectService(Config(tmp_path / "ui-config.json")), tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    return window


def test_startup_actions_and_empty_state(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    assert window.stack.currentIndex() == 0
    assert window.drop_hint.isVisible()
    assert window.new_button.isEnabled() and window.open_button.isEnabled() and window.open_pdf_button.isEnabled()
    assert window.recent_empty.isVisible() and not window.recent.isVisible()
    assert not window.toolbar.isVisible()


def test_workspace_shell_modes_focus_and_sizes(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    window.service.create_project(tmp_path, "漫画工作台")
    window._project_opened()
    workspace = window.workspace
    assert window.toolbar.isVisible()
    assert workspace.tool_rail.isVisible()
    assert [workspace.left_tabs.tabText(i) for i in range(4)] == [
        window.language.tr(key) for key in ("panel.pages", "panel.ocr_text", "panel.batches", "panel.project")]
    assert workspace.right_tabs.count() == 6
    assert not workspace.right_tabs.isTabVisible(5)
    window.simple_action.setChecked(False)
    assert workspace.right_tabs.isTabVisible(5)
    window.simple_action.setChecked(True)
    assert not workspace.right_tabs.isTabVisible(5)
    for width, height in ((1366, 768), (1920, 1080), (2560, 1440)):
        window.resize(width, height)
        qtbot.wait(30)
        assert workspace.canvas.width() >= 500
        assert workspace.right_tabs.width() >= 300
    window.toggle_focus()
    assert workspace.canvas.isVisible() and window.toolbar.isVisible()
    assert not workspace.tool_rail.isVisible() and not workspace.left_tabs.isVisible()
    window.toggle_focus()
    assert workspace.tool_rail.isVisible() and workspace.left_tabs.isVisible()


def test_toolbar_actions_and_translation_primary(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    window.service.create_project(tmp_path, "Toolbar")
    window._project_opened()
    workspace = window.workspace
    assert workspace.actions["pdf"] in window.workflow_buttons["import"][0].menu().actions()
    assert window.translation_scope_actions["page"] in window.workflow_buttons["translation"][0].menu().actions()
    assert workspace.actions["erase_refill"] not in window.toolbar.actions()
    assert window.toolbar.height() == 42
    assert workspace.erase_refill_button.property("variant") == "primary"
    assert workspace.block_translation.minimumHeight() >= 100
    workspace.left_tabs.setCurrentIndex(1)
    assert workspace.ocr_empty.isVisible()
    window.zoom_choice.setCurrentText("200%")
    window._apply_zoom_text()
    assert round(workspace.canvas.transform().m11(), 2) == 2
    window.zoom_choice.setCurrentText("Fit")
    window._apply_zoom_choice(0)
    assert workspace.canvas.fit_mode


def test_quality_dock_and_tool_rail(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    window.service.create_project(tmp_path, "Quality")
    window._project_opened()
    workspace = window.workspace
    workspace._show_quality_report({"counts": {"error": 0, "warning": 0, "info": 0}, "issues": []})
    assert workspace.bottom_tabs.currentIndex() == 3 and workspace.bottom_tabs.isVisible()
    workspace._activate_rail("hand")
    assert workspace.canvas.hand_tool and workspace.rail_buttons["hand"].isChecked()
    workspace._activate_rail("pointer")
    assert not workspace.canvas.hand_tool and workspace.rail_buttons["pointer"].isChecked()


def test_settings_navigator_uses_real_preferences(qtbot, tmp_path):
    from app.ui.settings_dialog import SettingsDialog
    window = make_window(qtbot, tmp_path)
    dialog = SettingsDialog(window)
    qtbot.addWidget(dialog)
    assert dialog.navigation.count() == 7
    dialog.simple.setChecked(False)
    assert not window.simple_action.isChecked()
    dialog.cache_size.setValue(128)
    assert window.service.config.image_cache_mb == 128
    assert window.workspace.cache.limit_bytes == 128 * 1024 * 1024
