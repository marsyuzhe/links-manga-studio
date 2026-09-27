"""R3 presentation gates; no network and no real desktop automation."""
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QListWidget, QMenu, QPushButton, QStyleOptionViewItem
from app.importers.image_importer import Candidate, ImportPreview
from app.ui.transfer_dialogs import ImportPreviewDialog, ExportOptionsDialog
from app.ui.components import exec_dialog
from app.ui.about_dialog import AboutDialog
from app.ui.font_picker import FontPicker
from app.ui.mask_editor import MaskDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.interaction import SelectionDelegate
from app.ui.translation_scope import page_ids
from app.translation.profiles import TranslationError
from test_ai_translation import ai_project
from test_product_060 import ready_window
from test_ui_design import make_window


@pytest.fixture(autouse=True)
def settle_windows(qtbot):
    yield
    from app.ui.window import MainWindow
    for window in QApplication.topLevelWidgets():
        if isinstance(window, MainWindow):
            qtbot.waitUntil(lambda: not window.workspace.jobs, timeout=15000)
            window.close()


@pytest.mark.parametrize('theme', ['dark', 'light'])
@pytest.mark.parametrize('language', ['zh_CN', 'en_US'])
def test_transfer_safe_insets_and_footer(qtbot, tmp_path, theme, language):
    w = make_window(qtbot, tmp_path); w.set_theme(theme); w.language.set_language(language)
    for d in (ImportPreviewDialog(ImportPreview(), w.language, w), ExportOptionsDialog(tmp_path, 3, w.language, w)):
        qtbot.addWidget(d); d.show(); qtbot.wait(10)
        assert d.layout().contentsMargins().right() == 16
        assert d.layout().contentsMargins().bottom() == 16
        box = d.findChild(QDialogButtonBox)
        assert box.button(QDialogButtonBox.StandardButton.Cancel).text() == w.language.tr('dialog.cancel')
        assert box.button(QDialogButtonBox.StandardButton.Cancel).property('variant') == 'ghost'
        assert d.rect().contains(box.geometry())
        d.close()


def test_import_duplicate_opt_in_and_cancel(qtbot, tmp_path):
    w = make_window(qtbot, tmp_path)
    preview = ImportPreview([Candidate(tmp_path/'one.png', {}, 'hash', True)])
    d = ImportPreviewDialog(preview, w.language, w); qtbot.addWidget(d)
    assert not d.include_duplicates and d.import_button.isEnabled()
    d.reject(); assert d.result() == QDialog.DialogCode.Rejected and not d.include_duplicates
    d.include_and_accept(); assert d.result() == QDialog.DialogCode.Accepted and d.include_duplicates
    empty = ImportPreviewDialog(ImportPreview(errors=['broken image']), w.language, w)
    qtbot.addWidget(empty); assert not empty.import_button.isEnabled()


def test_export_existing_format_quality_and_destination(qtbot, tmp_path):
    w = make_window(qtbot, tmp_path); d = ExportOptionsDialog(tmp_path, 20, w.language, w); qtbot.addWidget(d)
    assert d.destination.isReadOnly() and Path(d.destination.text()) == tmp_path/'exports'
    assert d.quality.text() == w.language.tr('ui.lossless')
    for fmt in ('jpg','webp'):
        d.format.setCurrentText(fmt); assert d.quality.text() == '90%'
    d.reject(); assert d.result() == 0


def test_about_copies_local_diagnostics_on_demand(qtbot, tmp_path, monkeypatch):
    w = make_window(qtbot, tmp_path); calls = []
    def info(*args): calls.append(args); return {'App Version':'0.6.0','Python':'fixture'}
    monkeypatch.setattr('app.ui.about_dialog.collect', info)
    d = AboutDialog(w); qtbot.addWidget(d); assert not calls
    d.diagnostics_button.click()
    assert calls and 'App Version: 0.6.0' in QApplication.clipboard().text()
    assert d.minimumWidth() >= 460


def test_one_shot_modal_is_disposed(qtbot, tmp_path):
    w = make_window(qtbot, tmp_path); destroyed = []
    d = QDialog(w); d.destroyed.connect(lambda: destroyed.append(True))
    QTimer.singleShot(0, d.accept)
    assert exec_dialog(d) == QDialog.DialogCode.Accepted
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert destroyed


def test_empty_cell_tooltip_does_not_crash(qtbot):
    view = QListWidget(); qtbot.addWidget(view); view.addItem(''); view.show()
    option = QStyleOptionViewItem(); option.initFrom(view); option.rect = QRect(0,0,200,30)
    event = QHelpEvent(QEvent.Type.ToolTip, QPoint(2,2), QPoint(2,2))
    assert SelectionDelegate(view).helpEvent(event, view, option, view.model().index(0,0))


def test_popup_tracks_open_state(qtbot, tmp_path):
    w = make_window(qtbot, tmp_path); button = QPushButton('Menu', w); menu = QMenu(button); menu.addAction('A')
    menu.popup(QPoint(50,50)); qtbot.wait(10); assert button.property('menuOpen') is True
    menu.hide(); assert button.property('menuOpen') is False


def test_quality_empty_and_project_mode_refresh(ai_project, qtbot):
    w = ready_window(ai_project, qtbot); ws = w.workspace
    ws._show_quality_report({'counts':{}, 'issues':[]})
    assert ws.quality_summary.text() == w.language.tr('quality.no_issues')
    w.simple_action.setChecked(False); assert ws.project_list.item(0).text() == str(ws.project)
    w.simple_action.setChecked(True); assert ws.project_list.item(0).text() == ws.project.stem
    ws.right_tabs.setCurrentIndex(2); assert ws.writing_mode_field.isVisible()


def test_scope_shared_preserves_order_and_validation(ai_project, qtbot):
    w = ready_window(ai_project, qtbot); ws = w.workspace
    assert page_ids(ws,'selected','3,1-2,2') == [p['id'] for p in ws.model.pages]
    with pytest.raises(TranslationError): page_ids(ws,'selected','0')
    with pytest.raises(TranslationError): page_ids(ws,'selected','4')
    assert page_ids(ws,'page') == [ws.current_id]


def test_settings_translation_remains_defaults_only(ai_project, qtbot):
    w = ready_window(ai_project, qtbot); d = SettingsDialog(w); qtbot.addWidget(d)
    d.show(); d.navigation.setCurrentRow(3)
    texts = [b.text() for b in d.pages.widget(3).findChildren(QPushButton)]
    assert len(texts) == 2
    assert d.navigation.count() == 7
    assert d.layout().contentsMargins().right() == 16


def test_font_preview_uses_current_translation_and_mask_locale(qtbot, tmp_path):
    from PySide6.QtGui import QImage
    w = make_window(qtbot,tmp_path)
    d = FontPicker(['Microsoft YaHei'], 'Microsoft YaHei', w, language=w.language, sample='当前译文')
    qtbot.addWidget(d); assert d.sample == '当前译文'
    mask = MaskDialog(QImage(100,100,QImage.Format.Format_RGB32), parent=w); qtbot.addWidget(mask)
    assert mask.windowTitle() == w.language.tr('mask.title')
    assert mask.layout().contentsMargins().right() == 16


def test_history_has_six_user_columns(ai_project, qtbot):
    w = ready_window(ai_project,qtbot); w.show_translation_center()
    assert w.translation_center.history.columnCount() == 6
    assert w.translation_center.error('unrecognized_fixture_code') == w.language.tr('ai.error_translation_failed')


def test_project_style_alignment_is_localized(ai_project, qtbot):
    from app.ui.project_styles import ProjectStylesDialog
    from app.styles.project_styles import ProjectStyleService
    w = ready_window(ai_project, qtbot)
    d = ProjectStylesDialog(ProjectStyleService(w.service.connection), w.language, lambda *args: None, w)
    qtbot.addWidget(d)
    assert [d.alignment.itemText(n) for n in range(3)] == [w.language.tr('style.'+k) for k in ('left','center','right')]


def test_standard_prompts_share_safe_footer(qtbot, tmp_path):
    from PySide6.QtWidgets import QMessageBox, QInputDialog
    w = make_window(qtbot, tmp_path)
    message = QMessageBox(QMessageBox.Icon.Question,'Question','Fixture',
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,w)
    prompt = QInputDialog(w); prompt.setLabelText('Fixture')
    for dialog in (message, prompt):
        qtbot.addWidget(dialog); dialog.show(); qtbot.wait(10)
        assert dialog.layout().contentsMargins().right() == 16
        assert dialog.layout().contentsMargins().bottom() == 16
        box = dialog.findChild(QDialogButtonBox)
        assert box.button(QDialogButtonBox.StandardButton.Cancel).text() == w.language.tr('dialog.cancel')
        dialog.close()


def test_context_uses_existing_actions(ai_project, qtbot):
    w = ready_window(ai_project,qtbot); ws = w.workspace; seen = []
    def inspect_and_close():
        for menu in ws.findChildren(QMenu):
            if menu.isVisible():
                seen.extend(menu.actions()); menu.close()
    QTimer.singleShot(100, inspect_and_close)
    ws._block_context_menu(ws.selected_block,QPoint(0,0))
    assert all(ws.actions[key] in seen for key in ('erase_refill','copy_style','paste_style','delete_block'))
    assert ws.actions['erase_quick'] not in seen
