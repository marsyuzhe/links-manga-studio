"""0.6.0 product behavior: compact UI, safe retries and large fake translation."""
import json,time,uuid,io
from dataclasses import replace
from http.client import RemoteDisconnected
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton
from app.config import Config
from app.project import ProjectService
from app.ui.window import MainWindow
from app.ui.translation_settings import ProfileEditor,ProjectTranslationDialog
from app.ui.translation_details import TranslationDetailsDialog
from app.translation.profiles import ProfileStore,ProviderProfile,TranslationError
from app.translation.providers import OpenAICompatibleTranslator,TranslationResult
from app.translation.tasks import create_translation_task,run_translation_task
from app.ocr.review import TextBlockService
from app.history import HistoryService
from test_ai_translation import ai_project,FakeProvider
import pytest


def ready_window(ai_project,qtbot):
    project,pages,blocks,profile,store=ai_project
    window=MainWindow(project,project.path/'logs/app.log');qtbot.addWidget(window)
    window.resize(1366,768);window.show();window._project_opened()
    qtbot.waitUntil(lambda:not window.workspace.jobs and window.workspace.canvas.page_id==pages[0],timeout=10000)
    window.workspace.select_block(blocks[0]);qtbot.wait(30)
    return window


def test_compact_controls_canvas_and_laptop_geometry(ai_project,qtbot):
    window=ready_window(ai_project,qtbot);ws=window.workspace
    visible=[b for b in window.findChildren(QAbstractButton) if b.isVisible()]
    assert len(visible)<=16
    assert window.height()==768 and window.width()==1366
    assert ws.canvas.width()>=650
    assert ws.right_tabs.parentWidget().width()>=300
    assert not ws.translation_notes.header.isChecked() and not ws.block_notes.isVisible()
    assert not ws.fill_only_button.isVisible() and not ws.bottom_tabs.isVisible()
    assert not ws.left_tabs.isTabVisible(3)
    assert set(window.workflow_buttons)=={'import','ocr','translation','export'}
    assert ws.erase_refill_button.property('variant')=='primary'
    window.close()


def test_manual_workflow_and_typing_do_not_trigger_tool_shortcuts(ai_project,qtbot):
    window=ready_window(ai_project,qtbot);ws=window.workspace
    window.workflow_buttons['translation'][0].click()
    assert window.stack.currentWidget() is window.translation_center
    window.show_manga();ws.open_translation_editor()
    assert ws.block_translation.hasFocus()
    qtbot.keyClicks(ws.block_translation,'test V T F')
    ws._save_translation_debounced()
    assert ws.block_translation.toPlainText()=='test V T F'
    assert ws.rail_buttons['pointer'].isChecked() and not ws.canvas.text_tool
    ws.translation_notes.header.setChecked(True)
    assert ws.block_notes.isVisible()
    window.close()


def test_profiles_parameters_and_glossary_progressive_disclosure(ai_project,qtbot):
    window=ready_window(ai_project,qtbot)
    project,pages,blocks,profile,store=ai_project
    dialog=ProfileEditor(store,window.language,profile,window);qtbot.addWidget(dialog);dialog.show()
    assert not dialog.fields['timeout'].isVisible()
    dialog.advanced.header.setChecked(True)
    assert dialog.fields['timeout'].isVisible()
    assert dialog.key.echoMode()==dialog.key.EchoMode.Password
    dialog.close()
    terms=ProjectTranslationDialog(project.connection,window.language,window);qtbot.addWidget(terms);terms.show()
    assert terms.tables['glossary'][0].isColumnHidden(3)
    assert terms.tables['character_notes'][0].isColumnHidden(2)
    assert not terms.instructions.isVisible()
    terms.advanced.header.setChecked(True)
    terms.context_mode.setCurrentIndex(2)
    assert terms.context.value()==2
    assert not terms.tables['glossary'][0].isColumnHidden(3)
    terms.close();window.close()


def test_provenance_dialog_contains_safe_metadata_not_source(ai_project,qtbot):
    project,pages,blocks,profile,store=ai_project
    from app.translation.service import TranslationService
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    service.apply(snapshots,FakeProvider().translate(payload),profile)
    window=ready_window(ai_project,qtbot)
    dialog=TranslationDetailsDialog(project.connection,blocks[0],window.language,window);qtbot.addWidget(dialog)
    assert 'key' not in ' '.join(label.text() for label in dialog.findChildren(__import__('PySide6.QtWidgets',fromlist=['QLabel']).QLabel))
    assert profile.model in window.workspace.ai_provenance.text()
    dialog.close();window.close()


@pytest.mark.parametrize('failure',['malformed','reset'])
def test_malformed_http_and_connection_reset_have_finite_retry(failure):
    waits=[]
    provider=OpenAICompatibleTranslator(ProviderProfile('mock','Mock','openai','https://example.invalid/v1','mock',max_retries=1),sleeper=waits.append)
    class Opener:
        calls=0
        def open(self,*a,**kw):
            self.calls+=1
            if self.calls==1:
                if failure=='reset':raise RemoteDisconnected('fixture')
                return io.BytesIO(b'not-json')
            return io.BytesIO(b'{"data":[{"id":"mock"}]}')
    opener=Opener();provider.opener=opener
    assert provider.test_connection()=='connected' and opener.calls==2 and waits==[2]


def test_malformed_exhaustion_is_safe():
    provider=OpenAICompatibleTranslator(ProviderProfile('mock','Mock','openai','https://example.invalid/v1','mock',max_retries=1),sleeper=lambda _:None)
    class Opener:
        calls=0
        def open(self,*a,**kw):self.calls+=1;return io.BytesIO(b'private-source-fixture')
    provider.opener=Opener()
    with pytest.raises(TranslationError,match='invalid_output'):provider.detect_models()
    assert provider.opener.calls==2


def test_task_progress_does_not_force_open_dock(ai_project,qtbot):
    window=ready_window(ai_project,qtbot);ws=window.workspace
    from threading import Event
    release=Event()
    ws.run_job(lambda progress,cancel:(progress(42,100,'status.ai_translation'),release.wait(2),{})[-1],lambda result:None,'ai.translate')
    qtbot.waitUntil(lambda:'42%' in window.task_indicator.text())
    assert window.task_indicator.isVisible() and not ws.bottom_tabs.isVisible()
    window.task_indicator.click()
    assert ws.bottom_tabs.isVisible() and ws.bottom_tabs.currentIndex()==0
    release.set();qtbot.waitUntil(lambda:not ws.jobs)
    assert not window.task_indicator.isVisible()
    window.close()


def test_thousand_page_fake_translation_preserves_protected_text(project_factory,tmp_path):
    project=project_factory('AI千页')
    db=project.connection;project_id=db.execute('SELECT id FROM projects').fetchone()[0]
    pages=[str(uuid.uuid4()) for _ in range(1000)]
    blocks=[str(uuid.uuid4()) for _ in pages]
    with db:
        db.executemany('INSERT INTO pages(id,project_id,page_uid,display_order,width,height) VALUES(?,?,?,?,400,600)',[(pid,project_id,f'P{i:04d}',i) for i,pid in enumerate(pages,1)])
        db.executemany("INSERT INTO text_blocks(id,page_id,text_uid,sequence,reading_order,bbox_json,source_text) VALUES(?,?,?,1,1,'[10,10,100,100]','fixture')",[(bid,pid,f'P{i:04d}-T001') for i,(bid,pid) in enumerate(zip(blocks,pages),1)])
    TextBlockService(db).save_translation(blocks[0],'protected manual')
    profile=ProviderProfile('large-fixture','Fixture','ollama',model='mock')
    store=ProfileStore(Config(tmp_path/'profiles.json'));store.save(profile)
    tid=create_translation_task(db,pages,profile.id)
    start=time.monotonic();result=run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())
    assert result['completed']==1000 and result['items'].get('failed',0)==0
    assert TextBlockService(db).translation(blocks[0])['text']=='protected manual'
    assert db.execute("SELECT count(*) FROM translations WHERE status='ai_draft'").fetchone()[0]==999
    assert HistoryService(db).undo()
    print('1000-page fake translation seconds:',round(time.monotonic()-start,3))


def test_disabled_profile_remains_editable_but_cannot_run(ai_project,qtbot):
    from app.ui.settings_dialog import SettingsDialog
    project,pages,blocks,profile,store=ai_project
    profile=replace(profile,enabled=False);store.save(profile)
    project.config.data['translation_profiles']=store.config.data['translation_profiles']
    project.config.data['translation_mode']='local'
    window=ready_window(ai_project,qtbot)
    settings=SettingsDialog(window);qtbot.addWidget(settings)
    assert settings.translation_settings.profiles.count()==1
    window.show_translation_center()
    assert window.translation_center.store.get(profile.id,enabled_only=False).enabled is False
    assert window.translation_center.services.rowCount()==1
    assert window.translation_center.provider.count()==0
    with pytest.raises(TranslationError,match='profile_unavailable'):store.get(profile.id)
    settings.close();window.close()
