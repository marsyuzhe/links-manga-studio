"""Small noninteractive checks for the packaged Windows runtime."""
from __future__ import annotations

import sqlite3
import uuid
import json
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter

from .config import Config
from .i18n import LanguageManager
from .images.image_loader import ImageLoader
from .ocr.pipeline import ModelManager, RapidBackend
from .project import ProjectService
from .resources import resource_path
from .database.schema import VERSION
from .branding import DISPLAY_NAME, AUTHOR_EN
from .themes.manager import ThemeManager


def run_release_smoke(output: Path) -> dict:
    checks: dict[str, str] = {}
    base = output.parent.resolve()
    base.mkdir(parents=True, exist_ok=True)

    icon = QIcon(str(resource_path("assets/icons/app_icon.ico")))
    if icon.isNull():
        raise RuntimeError("Bundled icon cannot be loaded")
    checks["icon"] = "PASS"

    config = Config(base / "smoke-config.json")
    if DISPLAY_NAME != "Links Manga Studio" or AUTHOR_EN != "Links Tam":
        raise RuntimeError("Product identity mismatch")
    checks["brand_about"] = "PASS"
    theme = ThemeManager(config)
    for mode in ("dark", "light", "system"):
        theme.set_mode(mode)
        if theme.effective not in ("dark", "light") or not theme.tokens["window_bg"]:
            raise RuntimeError(f"Theme failed: {mode}")
    checks["themes"] = "PASS"
    language = LanguageManager(config)
    for locale in ("zh_CN", "en_US"):
        language.set_language(locale)
        if not language.tr("action.new_project") or language.tr("action.new_project") == "action.new_project":
            raise RuntimeError(f"Locale failed: {locale}")
        checks[f"locale_{locale}"] = "PASS"

    service = ProjectService(config)
    project = service.create_project(base, f"发布验收-{uuid.uuid4().hex[:8]}")
    service.close_project()
    service.open_project(project)
    if service.connection is None:
        raise RuntimeError("Project database was not reopened")
    db = service.connection
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("SQLite foreign keys disabled")
    if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
        raise RuntimeError("SQLite WAL disabled")
    checks["project_sqlite"] = "PASS"
    from .styles.project_styles import ProjectStyleService
    from .history import HistoryService
    styles = ProjectStyleService(db)
    if len(styles.list_presets()) != 6 or db.execute("PRAGMA user_version").fetchone()[0] != VERSION:
        raise RuntimeError("Project style presets or schema version missing")
    styles.update_preset("speech", {"font": "Arial"})
    if not HistoryService(db).undo() or not HistoryService(db).redo():
        raise RuntimeError("Project style undo/redo failed")
    checks["project_styles"] = "PASS"
    service.close_project()

    legacy = service.create_project(base, f"迁移验收-{uuid.uuid4().hex[:8]}")
    service.close_project()
    with sqlite3.connect(legacy / "project.sqlite3") as old:
        old.execute("DROP TABLE text_style_presets")
        old.execute("ALTER TABLE text_blocks DROP COLUMN style_role")
        old.execute("ALTER TABLE text_blocks DROP COLUMN style_override_json")
        old.execute("UPDATE projects SET schema_version=3")
        old.execute("PRAGMA user_version=3")
    service.open_project(legacy)
    if service.connection.execute("PRAGMA user_version").fetchone()[0] != VERSION:
        raise RuntimeError("v3 to v4 migration failed")
    if not list((legacy / "backups").glob("before-schema-v4-*.sqlite3")):
        raise RuntimeError("Migration backup missing")
    service.close_project()
    checks["migration_v4"] = "PASS"

    image = QImage(320, 100, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.setFont(QFont("Arial", 22))
    painter.drawText(10, 65, "MANGA 123")
    painter.end()
    image_path = base / "第001页.png"
    if not image.save(str(image_path)) or ImageLoader().load(image_path).isNull():
        raise RuntimeError("Bundled image loader failed")
    checks["image"] = "PASS"

    from .rendering.fonts import FontCatalog
    records = FontCatalog(base / "font_catalog.json").metadata()
    if not records or not FontCatalog(base / "font_catalog.json").search(records[0]["family"]):
        raise RuntimeError("Bundled font catalog failed")
    checks["font_cache"] = "PASS"

    from .pdf.render import PdfRenderService
    import pypdfium2 as pdfium
    if not hasattr(pdfium, "PdfDocument") or not PdfRenderService(project):
        raise RuntimeError("PDFium backend failed")
    checks["pdfium"] = "PASS"

    from .documents.word import WordExchange
    from .rendering.renderer import PageRenderer, fit_font
    from .rendering.layout import fit_layout
    from .importers.folder_importer import scan_files
    from .importers.image_importer import ImageImporter
    from .pages.page_service import PageService
    from .quality.checker import QualityChecker
    if not WordExchange or not fit_font:
        raise RuntimeError("Word or renderer import failed")
    checks["word_renderer"] = "PASS"

    service.open_project(project)
    importer = ImageImporter(project)
    if importer.commit(importer.validate(scan_files([image_path]))) != 1:
        raise RuntimeError("Packaged image importer failed")
    db = service.connection
    page = PageService(db, project).list_pages()[0]
    block_id = str(uuid.uuid4())
    with db:
        db.execute("""INSERT INTO text_blocks
            (id,page_id,text_uid,sequence,reading_order,bbox_json,source_text,ocr_confidence)
            VALUES(?,?,?,?,?,?,?,?)""", (block_id, page["id"], page["page_uid"] + "-T001", 1, 1,
                                    json.dumps([10, 10, 180, 80]), "MANGA", .9))
    report = QualityChecker(db, records).scan()
    if not any(issue["code"] == "translation_empty" for issue in report["issues"]):
        raise RuntimeError("Packaged quality checker failed")
    checks["quality_check"] = "PASS"
    if fit_layout("中文译文", json.loads(ProjectStyleService(db).preset("speech")["settings_json"]), 200, 100).status == "overflow":
        raise RuntimeError("Packaged layout engine failed")
    if PageRenderer(db, project).render_page(page).isNull():
        raise RuntimeError("Packaged renderer failed")
    checks["renderer_layout"] = "PASS"
    from .ocr.review import TextBlockService
    TextBlockService(db).save_translation(block_id,"人工译文")
    if TextBlockService(db).translation(block_id)["status"] != "human_edited":
        raise RuntimeError("Manual translation failed")
    checks["translation_manual"] = "PASS"
    _ai_mock_smoke(service,config,checks)
    _r2_ui_smoke(service,config,checks)
    service.close_project()

    models = ModelManager().status()
    if not models["installed"]:
        raise RuntimeError(f"Bundled OCR models missing: {models['missing']}")
    backend = RapidBackend()
    backend.recognize(image)
    checks["rapidocr_inference"] = "PASS"
    return {"ok": True, "checks": checks, "project": str(project),
            "ocr_engine": backend.name, "ocr_model": backend.model,
            "sqlite_version": sqlite3.sqlite_version}


def _ai_mock_smoke(service,config,checks):
    """Loopback mock protocols only; never load a user's key or call a paid API."""
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    from .translation.profiles import ProfileStore,ProviderProfile
    from .translation.providers import provider_for
    from .translation.tasks import create_translation_task,run_translation_task
    from .translation.service import TranslationService
    from .history import HistoryService
    from .ocr.review import TextBlockService
    from .batches.service import BatchService
    from .documents.word import WordExchange
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value):
            data=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            self.reply({'models':[{'name':'mock'}]} if self.path=='/api/tags' else {'data':[{'id':'mock'}]})
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            payload=json.loads(body['messages'][-1]['content'])
            content=json.dumps([{'id':b['id'],'translation':'合成译文'} for b in payload['target']],ensure_ascii=False)
            self.reply({'message':{'content':content},'prompt_eval_count':2,'eval_count':3} if self.path=='/api/chat' else
                {'choices':[{'message':{'content':content}}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        for kind in ('openai','ollama','local_openai'):
            profile=ProviderProfile('mock-'+kind,'Runtime fixture',kind,base if kind=='ollama' else base+'/v1','mock',max_retries=0)
            provider=provider_for(profile)
            if provider.test_connection()!='connected' or provider.translate({'target':[{'id':'fixture','source':'fixture'}]}).translations.get('fixture')!='合成译文':
                raise RuntimeError('Mock translation protocol failed')
            checks['ai_mock_'+kind]='PASS'
        db=service.connection;page=db.execute('SELECT id,page_uid FROM pages LIMIT 1').fetchone()
        block_id=str(uuid.uuid4())
        with db:
            db.execute("""INSERT INTO text_blocks(id,page_id,text_uid,sequence,reading_order,bbox_json,source_text)
                VALUES(?,?,?,2,2,'[10,10,180,80]','fixture')""",(block_id,page['id'],page['page_uid']+'-T002'))
        profile=ProviderProfile('task-mock','Runtime fixture','ollama',base,'mock',max_retries=0)
        store=ProfileStore(config);store.save(profile)
        task=create_translation_task(db,[page['id']],profile.id)
        result=run_translation_task(service.path,store,task)
        if result['completed']!=1 or TextBlockService(db).translation(block_id)['status']!='ai_draft':
            raise RuntimeError('Packaged translation task failed')
        if not HistoryService(db).undo() or not HistoryService(db).redo():
            raise RuntimeError('AI translation Undo failed')
        TranslationService(db).mark_reviewed(block_id)
        batch=BatchService(db).create_for_unassigned()[0]
        exchange=WordExchange(db,service.path)
        path=exchange.export(batch,'light')
        if exchange.import_document(path)['imported']<2:
            raise RuntimeError('Packaged DOCX roundtrip failed')
        checks['ai_tasks_review_undo']='PASS'
        checks['docx_roundtrip']='PASS'
    finally:
        server.shutdown();server.server_close();thread.join()


def _r2_ui_smoke(service,config,checks):
    """Packaged native UI wiring only; does not test visible Windows UX."""
    import time
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPixmap
    from .ui.window import MainWindow
    from .translation.glossary import GlossaryService
    window=MainWindow(service,service.path/'logs/app.log');window.show();window._project_opened()
    limit=time.monotonic()+15
    while window.workspace.jobs and time.monotonic()<limit:
        QApplication.processEvents();time.sleep(.01)
    if window.workspace.jobs:raise RuntimeError("UI fixture initialization timed out")
    window.show_translation_center('page')
    if window.stack.currentWidget() is not window.translation_center or window.translation_center.tabs.count()!=3:
        raise RuntimeError("Translation Center was not packaged")
    checks['translation_center_ui']='PASS'
    g=GlossaryService(service.connection);g.save({'source_term':'smoke-term','target_term':'验收术语','category':'other'})
    window.show_glossary()
    if window.glossary_workspace.table.rowCount()<1:raise RuntimeError('Glossary UI failed')
    checks['glossary_ui']='PASS'
    for mode in ('dark','light'):
        if QPixmap(str(resource_path('assets/icons/dropdown_'+mode+'.svg'))).isNull():raise RuntimeError('Dropdown SVG missing')
    checks['interaction_assets']='PASS'
    window.close()
