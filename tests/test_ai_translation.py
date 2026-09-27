"""No paid API or LLM download: synthetic project and loopback mock services."""
import json
import logging
import sqlite3
import threading
import uuid
import hashlib
from PIL import Image
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
import socket
import pytest

from app.config import Config
from app.history import HistoryService
from app.ocr.review import TextBlockService
from app.tasks.service import TaskService
from app.translation.profiles import ProviderProfile, ProfileStore, TranslationError
from app.translation.providers import (ManualTranslator, OpenAICompatibleTranslator, OllamaTranslator,
    LocalOpenAICompatibleTranslator, TranslationResult, validate_output, messages)
from app.translation.service import TranslationService
from app.translation.tasks import create_translation_task, run_translation_task


class MemorySecrets:
    def __init__(self): self.values = {}
    def set(self, pid, value): self.values[pid] = value
    def get(self, pid): return self.values.get(pid, "")


@pytest.fixture
def ai_project(project_factory, tmp_path):
    project = project_factory()
    ids, blocks = [], []
    with project.connection:
        for n in range(1, 4):
            pid = str(uuid.uuid4()); ids.append(pid)
            source_id = str(uuid.uuid4())
            path = project.path / 'sources' / f'fixture{n}.png'
            Image.new('RGB',(400,600),'white').save(path)
            project_id = project.connection.execute("SELECT id FROM projects").fetchone()[0]
            project.connection.execute("INSERT INTO source_files(id,project_id,kind,original_path,stored_path,sha256,size_bytes) VALUES(?,?,'image',?,?,?,?)",
                (source_id,project_id,str(path),f'sources/fixture{n}.png',hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_size))
            project.connection.execute("INSERT INTO pages(id,project_id,page_uid,display_order,width,height,source_file_id) VALUES(?,?,?,?,400,600,?)",
                (pid, project_id, f"P{n:04d}", n, source_id))
            for order in (2, 1):
                bid = str(uuid.uuid4()); blocks.append(bid)
                project.connection.execute("""INSERT INTO text_blocks(id,page_id,text_uid,sequence,reading_order,bbox_json,source_text)
                    VALUES(?,?,?,?,?,'[10,10,200,100]',?)""", (bid,pid,f"P{n:04d}-T{order:03d}",order,order,f"hello {n}/{order}"))
    profile = ProviderProfile("fixture-profile", "Fixture", "ollama", model="mock")
    store = ProfileStore(Config(tmp_path / "app-config.json"), MemorySecrets())
    store.save(profile)
    return project, ids, blocks, profile, store


class FakeProvider:
    def __init__(self, fail=None, stop=None): self.calls=[]; self.fail=fail; self.stop=stop
    def translate(self, payload, stop=None):
        self.calls.append(payload)
        if self.fail and payload["target"][0]["id"].startswith(self.fail):
            raise TranslationError("timeout")
        if self.stop: self.stop.set()
        return TranslationResult({b["id"]:"译文 " + b["id"] for b in reversed(payload["target"])},
                                 {"prompt_tokens": 4,"completion_tokens": 2,"total_tokens":6},20)


def test_manual_provider_has_no_network():
    assert ManualTranslator().translate({"target":[{"id":"T1","translation":"人工"}]}).translations == {"T1":"人工"}


@pytest.mark.parametrize("output,code", [
    ([{"id":"bad","translation":"x"}],"unknown_uid"),
    ([{"id":"a","translation":"x"},{"id":"a","translation":"y"}],"duplicate_uid"),
    ([],"missing_uid"),([{"id":"a","translation":" "}],"empty_translation"),
    ({"id":"a","translation":"x"},"invalid_output"),
    ([{"id":"a","translation":3}],"invalid_output"),
    ([{"id":"a","translation":"x","extra":1}],"invalid_output"),
    ("not JSON","invalid_output")])
def test_structured_rejection(output,code):
    with pytest.raises(TranslationError,match=code): validate_output(output,["a"])


def test_uid_mapping_ignores_output_order():
    assert validate_output('[{"id":"b","translation":"乙"},{"id":"a","translation":"甲"}]',["a","b"]) == {"b":"乙","a":"甲"}


@pytest.fixture
def mock_server():
    state={"calls":[],"failures":0,"failure_status":429}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self, data, status=200):
            raw=json.dumps(data).encode(); self.send_response(status)
            self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            self.send({"models":[{"name":"mock"}]} if self.path == '/api/tags' else {"data":[{"id":"mock"}]})
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['calls'].append(body)
            if state['failures']:
                state['failures']-=1; self.send({"error":"do not echo body"},state['failure_status']);return
            payload=json.loads(body['messages'][1]['content'])
            content=json.dumps([{"id":b['id'],"translation":"译文"} for b in reversed(payload['target'])])
            self.send({"message":{"content":content},"prompt_eval_count":3,"eval_count":2} if self.path=='/api/chat'
                else {"choices":[{"message":{"content":content}}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',state
    server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('kind,cls',[('openai',OpenAICompatibleTranslator),('ollama',OllamaTranslator),('local_openai',LocalOpenAICompatibleTranslator)])
def test_mock_http_providers_connection_and_usage(mock_server,kind,cls):
    url,state=mock_server
    profile=ProviderProfile('test','Test',kind,url if kind=='ollama' else url+'/v1','mock',max_retries=0)
    provider=cls(profile)
    assert provider.test_connection()=='connected'
    result=provider.translate({'target':[{'id':'b','source':'two'},{'id':'a','source':'one'}]})
    assert set(result.translations)=={'a','b'} and result.usage['total_tokens']==5


@pytest.mark.parametrize('status',[429,500,503])
def test_rate_limit_controlled_retry(mock_server,status):
    url,state=mock_server;state['failures']=1;state['failure_status']=status; waits=[]
    provider=OpenAICompatibleTranslator(ProviderProfile('test','Test','openai',url+'/v1','mock',max_retries=1),sleeper=waits.append)
    assert provider.translate({'target':[{'id':'a','source':'hi'}]}).translations['a']=='译文'
    assert len(state['calls'])==2 and waits==[2]


def test_timeout_is_safe_code():
    p=OpenAICompatibleTranslator(ProviderProfile('t','T','openai','https://example.invalid/v1','mock',max_retries=0))
    class Opener:
        def open(self,*args,**kwargs): raise URLError(socket.timeout('private details'))
    p.opener=Opener()
    with pytest.raises(TranslationError,match='timeout'):p.detect_models()


@pytest.mark.parametrize('url',['https://example.com/v1','http://203.0.113.1:1234/v1','http://user:password@localhost/v1','http://localhost/v1?token=example'])
def test_local_endpoint_restrictions(url):
    with pytest.raises(TranslationError):ProviderProfile('t','T','local_openai',url,'mock').validate()


def test_context_glossary_character_reading_order(ai_project):
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection)
    service.replace_terms([{'source_term':'hello','target_term':'你好','exact_match':True}],
                          [{'name':'Alice','translated_name':'爱丽丝','speech_style':'gentle'}])
    payload,_=service.prepare(pages[1])
    assert [b['id'] for b in payload['target']]==['P0002-T001','P0002-T002']
    assert [c['page_uid'] for c in payload['context']]==['P0001','P0003']
    assert payload['glossary'][0]['target_term']=='你好'
    assert 'gentle' in messages(payload)[1]['content']
    service.save_settings({'context_pages':0})
    assert service.prepare(pages[1])[0]['context']==[]


@pytest.mark.parametrize('reviewed',[False,True])
def test_human_and_reviewed_protection(ai_project,reviewed):
    project,pages,blocks,profile,store=ai_project
    review=TextBlockService(project.connection);review.save_translation(blocks[0],'人工译文')
    service=TranslationService(project.connection)
    if reviewed:service.mark_reviewed(blocks[0])
    payload,_=service.prepare(pages[0])
    assert len(payload['target'])==1
    assert len(service.prepare(pages[0],{'overwrite_protected':True})[0]['target'])==2


def test_page_batch_provenance_undo_and_manual_edit(ai_project):
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    service.apply(snapshots,FakeProvider().translate(payload),profile)
    review=TextBlockService(project.connection)
    assert review.translation(blocks[0])['source']=='ai_local'
    assert review.translation(blocks[0])['status']=='ai_draft'
    assert service.prepare(pages[0])[0]['target']==[]
    assert HistoryService(project.connection).undo()
    assert review.translation(blocks[0]) is None and review.translation(blocks[1]) is None
    assert HistoryService(project.connection).redo()
    review.save_translation(blocks[0],'人工修改')
    assert review.translation(blocks[0])['status']=='human_edited'


def test_stale_response_cannot_overwrite_human_edit(ai_project):
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    TextBlockService(project.connection).save_translation(blocks[0],'正在编辑')
    with pytest.raises(TranslationError,match='stale_translation'):service.apply(snapshots,FakeProvider().translate(payload),profile)
    assert TextBlockService(project.connection).translation(blocks[0])['text']=='正在编辑'


def test_persistent_failure_isolation_retry_and_usage(ai_project):
    project,pages,blocks,profile,store=ai_project
    tid=create_translation_task(project.connection,pages,profile.id)
    bad=FakeProvider(fail='P0002')
    result=run_translation_task(project.path,store,tid,factory=lambda p:bad)
    assert result['completed']==2 and result['items']['failed']==1
    good=FakeProvider()
    result=run_translation_task(project.path,store,tid,retry_failed=True,factory=lambda p:good)
    assert result['completed']==3 and len(good.calls)==1 and result['usage']['total_tokens']==18


def test_pause_and_reopen_resume(ai_project):
    project,pages,blocks,profile,store=ai_project;stop=threading.Event()
    tid=create_translation_task(project.connection,pages,profile.id)
    stop.set()
    assert run_translation_task(project.path,store,tid,stop=stop,factory=lambda p:FakeProvider())['status']=='paused'
    assert run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())['completed']==3


def test_pause_inflight_preserves_results_then_resumes(ai_project):
    project,pages,blocks,profile,store=ai_project;stop=threading.Event()
    tid=create_translation_task(project.connection,pages,profile.id)
    result=run_translation_task(project.path,store,tid,stop=stop,factory=lambda p:FakeProvider(stop=stop))
    assert result['status']=='paused' and result['completed']==1
    assert project.connection.execute('SELECT COUNT(*) FROM translations').fetchone()[0]==2
    assert run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())['completed']==3


def test_real_windows_credential_roundtrip_and_cleanup():
    from app.translation.profiles import WindowsSecrets
    vault=WindowsSecrets();pid='test-'+str(uuid.uuid4())
    try:
        vault.set(pid,'synthetic-credential')
        assert vault.get(pid)=='synthetic-credential'
    finally:
        vault.delete(pid)


def test_genuine_v4_migration_preserves_manual_translation(ai_project):
    from app.database.schema import VERSION
    project,pages,blocks,profile,store=ai_project
    TextBlockService(project.connection).save_translation(blocks[0],'旧版人工译文')
    path=project.path;project.close_project()
    with sqlite3.connect(path/'project.sqlite3') as db:
        for col in ('provider_profile_id','provider','model','prompt_version','created_at'):
            db.execute(f'ALTER TABLE translations DROP COLUMN {col}')
        db.execute('ALTER TABLE tasks DROP COLUMN options_json')
        db.execute('ALTER TABLE task_items DROP COLUMN usage_json')
        db.execute('ALTER TABLE task_items DROP COLUMN duration_ms')
        for table in ('project_translation_settings','glossary','character_notes'):
            db.execute(f'DROP TABLE {table}')
        db.execute('UPDATE projects SET schema_version=4');db.execute('PRAGMA user_version=4')
    metadata=json.loads((path/'project.json').read_text(encoding='utf-8'));metadata['schema_version']=4
    (path/'project.json').write_text(json.dumps(metadata),encoding='utf-8')
    project.open_project(path)
    assert project.connection.execute('PRAGMA user_version').fetchone()[0]==VERSION
    assert TextBlockService(project.connection).translation(blocks[0])['text']=='旧版人工译文'
    assert TextBlockService(project.connection).translation(blocks[0])['status']=='human_edited'
    assert list((path/'backups').glob('before-schema-v5-*.sqlite3'))


def test_ai_draft_docx_roundtrip_becomes_human_edited(ai_project):
    from app.batches.service import BatchService
    from app.documents.word import WordExchange
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    service.apply(snapshots,FakeProvider().translate(payload),profile)
    batch=BatchService(project.connection).create_for_unassigned()[0]
    word=WordExchange(project.connection,project.path);document=word.export(batch,'light')
    report=word.import_document(document)
    assert report['imported']>=2
    assert TextBlockService(project.connection).translation(blocks[0])['status']=='human_edited'


def test_reviewed_status_survives_erase_refill(ai_project):
    from app.workflow import WorkflowService
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    service.apply(snapshots,FakeProvider().translate(payload),profile)
    service.mark_reviewed(blocks[0])
    review=TextBlockService(project.connection);value=review.translation(blocks[0])['text']
    WorkflowService(project.connection,project.path).erase_and_refill(blocks[0],value)
    assert review.translation(blocks[0])['status']=='reviewed'


def test_interrupted_recovery(ai_project):
    project,pages,blocks,profile,store=ai_project
    tid=create_translation_task(project.connection,pages,profile.id)
    with project.connection:
        project.connection.execute("UPDATE tasks SET status='running' WHERE id=?",(tid,))
        project.connection.execute("UPDATE task_items SET status='running' WHERE task_id=?",(tid,))
    assert TaskService(project.connection).recover_interrupted()==1
    assert run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())['completed']==3


def test_cloud_consent_key_not_in_config_db_logs(ai_project,caplog):
    project,pages,blocks,profile,store=ai_project
    cloud=replace(profile,provider_type='openai',base_url='https://example.invalid/v1')
    secret='fixture-sensitive-value-not-a-real-key'
    store.save(cloud,secret)
    tid=create_translation_task(project.connection,pages,cloud.id)
    with pytest.raises(TranslationError,match='cloud_consent_required'):
        run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())
    store.consent(cloud)
    with caplog.at_level(logging.INFO):run_translation_task(project.path,store,tid,factory=lambda p:FakeProvider())
    assert secret not in caplog.text
    assert secret not in store.config.path.read_text()
    assert secret not in '\n'.join(project.connection.iterdump())
    assert not store.consented(replace(cloud,base_url='https://different.invalid/v1'))


def test_quality_ai_draft_is_warning(ai_project,qapp):
    from app.quality.checker import QualityChecker
    project,pages,blocks,profile,store=ai_project
    service=TranslationService(project.connection);payload,snapshots=service.prepare(pages[0])
    service.apply(snapshots,FakeProvider().translate(payload),profile)
    issues=QualityChecker(project.connection).scan()['issues']
    assert any(i['code']=='ai_draft_unreviewed' and i['severity']=='warning' for i in issues)


def test_ai_ui_scope_preview_settings(ai_project,qtbot):
    from app.ui.window import MainWindow
    from app.ui.settings_dialog import SettingsDialog
    from app.ui.ai_translation import TranslationRangeDialog
    project,pages,blocks,profile,store=ai_project
    project.config.data['translation_profiles']=store.config.data['translation_profiles']
    project.config.data['translation_mode']='local'
    window=MainWindow(project,project.path/'logs/app.log');qtbot.addWidget(window)
    window._project_opened();qtbot.waitUntil(lambda:not window.workspace.jobs,timeout=10000)
    settings=SettingsDialog(window);qtbot.addWidget(settings)
    assert settings.translation_settings.profiles.count()==2
    dialog=TranslationRangeDialog(window.workspace);qtbot.addWidget(dialog)
    dialog.scope.setCurrentIndex(4)
    assert '6' in dialog.preview_label.text()
    assert window.workspace.actions['ai_page'].isEnabled()
    window.workspace.jobs.append(object())
    window.workspace.update_actions()
    assert not window.workspace.actions['ai_page'].isEnabled()
    assert not window.workspace.actions['ai_next'].isEnabled()
    window.workspace.jobs.clear()
    window.workspace.update_actions()
    window.close()


def test_bounded_concurrency_and_page_commits(ai_project):
    from threading import Lock
    import time
    project,pages,blocks,profile,store=ai_project
    profile=replace(profile,max_concurrency=2)
    store.save(profile)
    lock=Lock()
    active=0
    peak=0
    class ConcurrentProvider(FakeProvider):
        def translate(self,payload,stop=None):
            nonlocal active,peak
            with lock:
                active+=1
                peak=max(peak,active)
            try:
                time.sleep(.08)
                return super().translate(payload,stop)
            finally:
                with lock: active-=1
    tid=create_translation_task(project.connection,pages,profile.id)
    result=run_translation_task(project.path,store,tid,factory=lambda p:ConcurrentProvider())
    assert result['completed']==3
    assert peak==2
    assert project.connection.execute("SELECT COUNT(*) FROM translations WHERE status='ai_draft'").fetchone()[0]==6


def test_task_creation_options_are_atomic(ai_project):
    project,pages,blocks,profile,store=ai_project
    before=project.connection.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    with pytest.raises(TypeError):
        TaskService(project.connection).create('AI_TRANSLATION',pages,options={'invalid':object()})
    assert project.connection.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==before
    assert project.connection.execute('SELECT COUNT(*) FROM task_items').fetchone()[0]==0


def test_ui_ai_job_updates_project_and_review_panel(ai_project,qtbot,monkeypatch):
    from app.ui.window import MainWindow
    from app.ui.ai_translation import start_task,reviewed
    project,pages,blocks,profile,store=ai_project
    project.config.data['translation_profiles']=store.config.data['translation_profiles']
    monkeypatch.setattr('app.translation.tasks.provider_for',lambda p,key:FakeProvider())
    window=MainWindow(project,project.path/'logs/app.log');qtbot.addWidget(window)
    window._project_opened();qtbot.waitUntil(lambda:not window.workspace.jobs,timeout=10000)
    ws=window.workspace
    tid=create_translation_task(project.connection,pages,profile.id)
    start_task(ws,tid)
    qtbot.waitUntil(lambda:not ws.jobs,timeout=10000)
    assert TaskService(project.connection).summary(tid)['completed']==3
    ws.select_block(blocks[0])
    assert ws.block_translation.toPlainText().startswith('译文')
    reviewed(ws)
    assert TextBlockService(project.connection).translation(blocks[0])['status']=='reviewed'
    window.close()
