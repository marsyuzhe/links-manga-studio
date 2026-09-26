"""Schema, inherited styles, font metadata, fitting and quality checks for 0.4."""
import json
import shutil
import sqlite3
from pathlib import Path

from app.database.schema import VERSION
from app.history import HistoryService
from app.project import ProjectService
from app.rendering.fonts import FontCatalog, FontPreferences
from app.rendering.layout import fit_layout, wrap_chinese
from app.rendering.font_match import recommend
from app.styles.project_styles import ProjectStyleService
from app.quality.checker import QualityChecker
from app.workflow import WorkflowService
from test_workflow_ui import prepare_block


def test_v3_to_v4_backup_and_styles(project_factory):
    service = project_factory()
    project = service.path
    service.close_project()
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("DROP TABLE text_style_presets")
        db.execute("ALTER TABLE text_blocks DROP COLUMN style_role")
        db.execute("ALTER TABLE text_blocks DROP COLUMN style_override_json")
        db.execute("UPDATE projects SET schema_version=3")
        db.execute("PRAGMA user_version=3")
    service.open_project(project)
    assert service.connection.execute("PRAGMA user_version").fetchone()[0] == VERSION
    assert len(list((project / "backups").glob("before-schema-v4-*.sqlite3"))) == 1
    assert len(ProjectStyleService(service.connection).list_presets()) == 6
    assert json.loads((project / "project.json").read_text(encoding="utf-8"))["schema_version"] == VERSION


def test_style_inherit_override_reset_and_undo(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    service = ProjectStyleService(project.connection)
    current = dict(project.connection.execute("SELECT * FROM text_blocks WHERE id=?", (block["id"],)).fetchone())
    assert service.resolve(current)["font"] == "Microsoft YaHei"
    service.update_preset("speech", {"font": "SimHei"})
    assert service.resolve(current)["font"] == "SimHei"
    service.set_override(block["id"], {"max_size": 40})
    current = dict(project.connection.execute("SELECT * FROM text_blocks WHERE id=?", (block["id"],)).fetchone())
    service.update_preset("speech", {"font": "SimSun", "max_size": 50})
    assert service.resolve(current)["font"] == "SimSun"
    assert service.resolve(current)["max_size"] == 40
    assert HistoryService(project.connection).undo()
    assert service.resolve(current)["font"] == "SimHei"
    assert HistoryService(project.connection).redo()
    assert service.resolve(current)["font"] == "SimSun"
    service.reset_override(block["id"])
    current = dict(project.connection.execute("SELECT * FROM text_blocks WHERE id=?", (block["id"],)).fetchone())
    assert service.resolve(current)["max_size"] == 50
    service.set_role(block["id"], "narration")
    assert project.connection.execute("SELECT style_role FROM text_blocks WHERE id=?", (block["id"],)).fetchone()[0] == "narration"


def test_font_metadata_cache_preferences_and_fallback(tmp_path):
    from app.config import Config
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    shutil.copy2(Path("C:/Windows/Fonts/arial.ttf"), fonts / "arial.ttf")
    catalog = FontCatalog(tmp_path / "font_cache.json", fonts)
    records = catalog.metadata()
    assert any(r["family"] == "Arial" and r["file_path"].endswith("arial.ttf") for r in records)
    assert catalog.metadata() == records
    assert catalog.search("ari")
    assert catalog.missing("not-installed")
    assert not catalog.supports_chinese("Arial")
    config = Config(tmp_path / "config.json")
    prefs = FontPreferences(config)
    prefs.toggle_favorite("Arial")
    prefs.used("Arial")
    assert FontPreferences(Config(config.path)).favorites == ["Arial"]
    assert FontPreferences(Config(config.path)).recent == ["Arial"]
    assert catalog.fallback("Arial", "中文") == "Arial"  # No CJK fallback in this isolated fixture.


def test_autofit_chinese_and_overflow(qapp):
    short = fit_layout("你好", {"font": "Microsoft YaHei", "min_size": 18, "max_size": 40, "padding": 8}, 200, 100)
    assert short.status in ("fit", "warning")
    assert short.font.pointSize() <= 40
    long = fit_layout("这是一段非常非常长的中文译文" * 4,
                      {"font": "Microsoft YaHei", "min_size": 18, "max_size": 40, "padding": 8}, 80, 40)
    assert long.status == "overflow" and long.font.pointSize() == 18
    from PySide6.QtGui import QFont, QFontMetrics
    lines = wrap_chinese("你好，世界", QFontMetrics(QFont("Microsoft YaHei", 18)), 42)
    assert all(not line.startswith("，") for line in lines)
    padded = fit_layout("你好世界", {"font": "Microsoft YaHei", "min_size": 18, "max_size": 40, "padding": 20}, 100, 60)
    assert padded.font.pointSize() <= short.font.pointSize()


def test_quality_detects_navigable_issues(qapp, project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    with project.connection:
        project.connection.execute("UPDATE text_blocks SET ocr_confidence=.3 WHERE id=?", (block["id"],))
    result = QualityChecker(project.connection).scan()
    codes = {issue["code"] for issue in result["issues"]}
    assert {"low_confidence", "translation_empty", "not_exported"} <= codes
    assert any(issue["block_id"] == block["id"] and issue["page_id"] == page["id"]
               for issue in result["issues"])
    WorkflowService(project.connection, project.path).erase_and_refill(block["id"], "译文" * 100)
    with project.connection:
        project.connection.execute("UPDATE text_blocks SET style_override_json=? WHERE id=?",
                                   (json.dumps({"font": "Missing Font"}), block["id"]))
    result = QualityChecker(project.connection, [{"family": "Arial", "supported_languages": [],
                                                  "category": "sans", "weight": 400, "italic": False}]).scan()
    codes = {issue["code"] for issue in result["issues"]}
    assert {"overflow", "font_missing", "style_inconsistent"} <= codes


def test_replace_missing_font_is_one_undo_step(project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    styles = ProjectStyleService(project.connection)
    styles.update_preset("speech", {"font": "Missing Font"})
    styles.set_override(block["id"], {"font": "Missing Font"})
    assert styles.replace_font("Missing Font", "Microsoft YaHei") == 2
    assert json.loads(styles.preset("speech")["settings_json"])["font"] == "Microsoft YaHei"
    assert HistoryService(project.connection).undo()
    assert json.loads(styles.preset("speech")["settings_json"])["font"] == "Missing Font"
    assert HistoryService(project.connection).redo()
    assert json.loads(styles.preset("speech")["settings_json"])["font"] == "Microsoft YaHei"


def test_batch_style_and_vertical_layout(qapp, project_factory, tmp_path):
    project, page, block = prepare_block(project_factory, tmp_path)
    styles = ProjectStyleService(project.connection)
    assert styles.apply_to_scope(block["id"], {"font": "SimHei"}, [page["id"]]) == 1
    assert HistoryService(project.connection).undo()
    current = dict(project.connection.execute("SELECT * FROM text_blocks WHERE id=?", (block["id"],)).fetchone())
    assert not json.loads(current["style_override_json"])
    vertical = fit_layout("竖排中文文字", {"font": "Microsoft YaHei", "writing_mode": "vertical",
                                         "min_size": 18, "max_size": 30, "padding": 4}, 120, 130)
    assert vertical.lines and vertical.status in ("fit", "warning")


def test_font_recommendation_is_qualitative(qapp):
    from PySide6.QtGui import QImage, QColor
    image = QImage(80, 80, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    records = [{"family": "Heavy Chinese", "category": "display", "weight": 700,
                "italic": False, "supported_languages": ["zh"]},
               {"family": "Arial", "category": "sans", "weight": 400,
                "italic": False, "supported_languages": []}]
    result = recommend(image, records)
    assert result and result[0]["family"] == "Heavy Chinese"
    assert result[0]["similarity"] in ("high", "medium", "low")


def test_font_browser_favorites_and_live_preview(qtbot, tmp_path):
    from app.config import Config
    from app.i18n import LanguageManager
    from app.ui.font_picker import FontPicker
    config = Config(tmp_path / "config.json")
    dialog = FontPicker([{"family": "Arial", "supported_languages": [], "file_path": "arial.ttf"}],
                        "Arial", config=config, language=LanguageManager(config), sample="你好")
    qtbot.addWidget(dialog)
    received = []
    dialog.preview_changed.connect(received.append)
    dialog.search.setText("ari")
    assert dialog.list.count() == 1
    dialog.list.setCurrentRow(0)
    dialog.favorite_button.click()
    dialog.scope.setCurrentIndex(2)
    assert dialog.list.count() == 1 and dialog.selected() == "Arial"
    assert received or dialog.preview.font().family() == "Arial"


def test_translation_debounce_and_quality_navigation(qtbot, project_factory, tmp_path):
    from app.ui.window import MainWindow
    from app.ocr.review import TextBlockService
    project, page, block = prepare_block(project_factory, tmp_path)
    window = MainWindow(project, tmp_path / "app.log")
    qtbot.addWidget(window)
    window.show()
    window._project_opened()
    qtbot.waitUntil(lambda: not window.workspace.jobs and window.workspace.canvas.page_id == page["id"], timeout=12000)
    workspace = window.workspace
    workspace.select_block(block["id"])
    workspace.block_translation.setPlainText("自动保存的译文")
    qtbot.waitUntil(lambda: (TextBlockService(project.connection).translation(block["id"]) or {}).get("text") == "自动保存的译文", timeout=3000)
    assert workspace.translation_status.text() == window.language.tr("status.saved")
    workspace._locate_quality_issue({"page_id": page["id"], "block_id": block["id"]})
    assert workspace.selected_block == block["id"]
    assert workspace.left_tabs.currentIndex() == 1
    window.close()


def test_project_style_dialog_applies_preset(qtbot, project_factory):
    from app.i18n import LanguageManager
    from app.ui.project_styles import ProjectStylesDialog
    project = project_factory()
    dialog = ProjectStylesDialog(ProjectStyleService(project.connection), LanguageManager(project.config),
                                 lambda *_args: None)
    qtbot.addWidget(dialog)
    dialog.font.setText("SimHei")
    dialog.apply_button.click()
    assert json.loads(ProjectStyleService(project.connection).preset("speech")["settings_json"])["font"] == "SimHei"
