"""Feature-free startup, bounded history and lazy view lifecycle."""
from app.ui.window import MainWindow
from app.project import ProjectService
from app.config import Config
from app.translation.tasks import create_translation_task
from test_ai_translation import ai_project
from test_product_060 import ready_window


def test_startup_never_contacts_providers_or_scans_fonts(qtbot,tmp_path,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('Unexpected startup work')
    monkeypatch.setattr('app.translation.profiles.WindowsSecrets.get',forbidden)
    monkeypatch.setattr('app.translation.providers.provider_for',forbidden)
    monkeypatch.setattr('app.rendering.fonts.FontCatalog.metadata',forbidden)
    monkeypatch.setattr('app.ocr.pipeline.RapidBackend.__init__',forbidden)
    w=MainWindow(ProjectService(Config(tmp_path/'config.json')),tmp_path/'app.log');qtbot.addWidget(w);w.show()
    assert w._translation_center is None and w._glossary_workspace is None
    assert not w.workspace.jobs
    w.language.set_language('en_US'); w.set_theme('light')
    assert w._translation_center is None and w._glossary_workspace is None
    w.close();assert w._translation_center is None


def test_project_open_does_not_build_hidden_views_or_scan_quality(ai_project,qtbot,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('Unexpected project-open scan')
    monkeypatch.setattr('app.quality.checker.QualityChecker.scan',forbidden)
    w=ready_window(ai_project,qtbot)
    assert w._translation_center is None and w._glossary_workspace is None
    w.close_project()
    assert w._translation_center is None and w._glossary_workspace is None


def test_lazy_views_created_once_and_hidden_polling_stops(ai_project,qtbot):
    w=ready_window(ai_project,qtbot);w.show_translation_center();c=w.translation_center
    assert c is w.translation_center and c.timer.isActive()
    assert w._glossary_workspace is None
    w.show_manga();assert not c.timer.isActive()
    w.show_translation_center();assert w.translation_center is c and c.timer.isActive()
    w.show_glossary();g=w.glossary_workspace
    assert g is w.glossary_workspace and not c.timer.isActive()
    w.show_manga();w.language.set_language('en_US')
    assert w._translation_center is None and w._glossary_workspace is None
    w.show_glossary();assert w.glossary_workspace.tabs.tabText(0)=='Terms'
    w.close()


def test_history_is_lazy_bounded_and_older_tasks_remain_accessible(ai_project,qtbot):
    project,pages,blocks,profile,store=ai_project
    for n in range(105):create_translation_task(project.connection,[pages[0]],profile.id,{'scope':'page','target_blocks':1})
    w=ready_window(ai_project,qtbot);w.show_translation_center();c=w.translation_center
    assert c.history.rowCount()==0
    c.tabs.setCurrentIndex(1);assert c.history.rowCount()==100 and c.history_more.isVisible()
    c.load_older_history();assert c.history.rowCount()==105 and not c.history_more.isVisible()
    w.close()
