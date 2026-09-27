"""All-surface geometry and curated snapshots; isolated synthetic data, offscreen."""
import json
import os
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', 'C:/Windows/Fonts')
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QApplication, QAbstractScrollArea, QDialog, QDialogButtonBox,
    QFileDialog, QInputDialog, QMessageBox, QMenu, QWidget)
from app.config import Config
from app.project import ProjectService
from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.pages.page_service import PageService
from app.ocr.pipeline import OCRPipeline
from app.ocr.review import TextBlockService
from app.translation.profiles import ProfileStore, ProviderProfile
from app.translation.tasks import create_translation_task
from app.tasks.service import TaskService
from app.styles.project_styles import ProjectStyleService
from app.ui.window import MainWindow, NewProjectDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.about_dialog import AboutDialog
from app.ui.font_picker import FontPicker
from app.ui.mask_editor import MaskDialog
from app.ui.project_styles import ProjectStylesDialog
from app.ui.translation_settings import ProfileEditor, ProjectTranslationDialog
from app.ui.ai_translation import TranslationRangeDialog
from app.ui.translation_details import TranslationDetailsDialog
from app.ui.glossary_workspace import TermEditor
from app.ui.transfer_dialogs import ImportPreviewDialog, ExportOptionsDialog
from tools.capture_ui_snapshots import sample_page, SampleOCR, spin, capture


def bounds(root):
    """Visible child bounds, excluding intentional scroll contents and popup windows."""
    issues = []
    checked = 0
    for child in root.findChildren(QWidget):
        if not child.isVisibleTo(root) or child.isWindow(): continue
        parent = child.parentWidget()
        if parent is None or child.objectName() in ('qt_scrollarea_viewport','qt_scrollarea_hcontainer','qt_scrollarea_vcontainer'): continue
        if isinstance(parent, QAbstractScrollArea): continue
        # A scroll content widget may exceed its viewport; its internal children must still fit it.
        if parent.objectName() == 'qt_scrollarea_viewport': continue
        if child.width() <= 0 or child.height() <= 0: continue
        checked += 1
        if not parent.rect().adjusted(-1,-1,1,1).contains(child.geometry()):
            issues.append({'child':type(child).__name__, 'name':child.objectName(),
                'parent':type(parent).__name__, 'rect':child.geometry().getRect(), 'bounds':parent.rect().getRect()})
    return checked, issues


def main():
    app = QApplication([])
    scale = os.environ.get('QT_SCALE_FACTOR','1')
    save = os.environ.get('LMW_R3_CAPTURE','0') == '1'
    output = Path('docs/ui_snapshots/0.6.0-r3'); output.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='lmw-r3-audit-', ignore_cleanup_errors=True) as temporary:
        root = Path(temporary); config = Config(root/'config.json'); config.data['language']='zh_CN'
        service = ProjectService(config); w = MainWindow(service, root/'app.log'); w.show()
        def check(name, widget, theme, size, snapshot=False, inset=False):
            app.processEvents(); widget.repaint(); app.processEvents()
            count, issues = bounds(widget)
            if inset and widget.layout():
                m = widget.layout().contentsMargins()
                if m.right()<16 or m.bottom()<16: issues.append({'inset':[m.right(),m.bottom()]})
            records.append({'surface':name,'theme':theme,'logical_size':size,'qt_scale':scale,
                'checked_children':count,'issues':issues,'status':'FAIL' if issues else 'PASS'})
            if save and snapshot: capture(widget,output/f'{name}_{theme}.png')
        for theme in ('dark','light'):
            w.set_theme(theme)
            for size in ((1366,768),(1600,900),(1920,1080),(2560,1440)):
                w.resize(*size); check('startup',w,theme,size,size==(1366,768))
        service.create_project(root,'界面验收','copy')
        source=root/'第001页.png'; sample_page(source)
        importer=ImageImporter(service.path); preview=importer.validate(scan_files([source])); importer.commit(preview)
        page=PageService(service.connection,service.path).list_pages()[0]
        OCRPipeline(service.connection,service.path,SampleOCR()).process_page(page)
        block=TextBlockService(service.connection).for_page(page['id'])[0]
        TextBlockService(service.connection).save_translation(block['id'],'当前译文，用于字体预览。')
        profile=ProviderProfile('r3-fixture','Local fixture','ollama',model='fixture')
        store=ProfileStore(config); store.save(profile)
        w._project_opened(); ws=w.workspace
        spin(app,lambda:not ws.jobs and ws.canvas.page_id==page['id']); ws.select_block(block['id'])
        for theme in ('dark','light'):
            w.set_theme(theme)
            for size in ((1366,768),(1600,900),(1920,1080),(2560,1440)):
                w.resize(*size); w.reset_panel_layout(); snap=size==(1366,768)
                w.show_manga(); ws.bottom_tabs.hide(); ws.left_tabs.setCurrentIndex(0)
                check('workspace',w,theme,size,snap)
                for index,name in enumerate(('translation','style','layout','source','erase')):
                    ws.right_tabs.setCurrentIndex(index); check('inspector_'+name,w,theme,size,snap and theme=='dark')
                for index,name in ((1,'ocr'),(2,'batches')):
                    ws.left_tabs.setCurrentIndex(index); check('left_'+name,w,theme,size,snap and theme=='dark')
                w.simple_action.setChecked(False); ws.left_tabs.setCurrentIndex(3); check('project_advanced',w,theme,size,snap and theme=='dark'); w.simple_action.setChecked(True)
                ws._show_quality_report({'counts':{},'issues':[]}); check('quality_empty',w,theme,size,snap)
                ws._show_quality_report({'counts':{'warning':1},'issues':[{'severity':'warning','code':'translation_empty','page_id':page['id'],'block_id':block['id']}]}); check('quality_issues',w,theme,size,snap and theme=='dark')
                for index,name in ((0,'tasks'),(1,'logs'),(2,'export_status')):
                    ws.bottom_tabs.setCurrentIndex(index); check(name,w,theme,size,snap and theme=='dark')
                ws.bottom_tabs.hide(); w.show_translation_center(); tc=w.translation_center; tc.timer.stop()
                for index,name in ((0,'translation_ready'),(1,'translation_history'),(2,'translation_services')):
                    tc.tabs.setCurrentIndex(index); check(name,w,theme,size,snap)
                tc.tabs.setCurrentIndex(0)
                task_id=create_translation_task(service.connection,[page['id']],profile.id,{'scope':'page','model':'fixture','target_blocks':1,'overwrite_protected':True})
                TaskService(service.connection).set_status(task_id,'running')
                with service.connection:
                    service.connection.execute("UPDATE task_items SET status='running' WHERE task_id=?",(task_id,))
                tc.task_id=task_id; tc.task_stack.setCurrentIndex(1); tc._last=None; tc.poll()
                check('translation_running',w,theme,size,snap and theme=='dark')
                with service.connection:
                    service.connection.execute("UPDATE task_items SET status='completed' WHERE task_id=?",(task_id,))
                    service.connection.execute("UPDATE tasks SET completed_units=1 WHERE id=?",(task_id,))
                    item_id=service.connection.execute('SELECT id FROM task_items WHERE task_id=?',(task_id,)).fetchone()[0]
                    service.connection.execute('INSERT INTO translation_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (task_id+'-fixture',task_id,item_id,page['id'],'ollama','fixture',1,1,'completed',None,'{}',1250,'2026-09-27T00:00:00+00:00'))
                TaskService(service.connection).set_status(task_id,'completed'); tc.poll(); check('translation_complete',w,theme,size,snap and theme=='dark')
                with service.connection:
                    service.connection.execute("UPDATE task_items SET status='failed',last_error='server_not_running' WHERE task_id=?",(task_id,))
                TaskService(service.connection).set_status(task_id,'failed'); tc.poll(); check('translation_error',w,theme,size,snap and theme=='dark')
                tc.new_task(); tc.connections.clear();
                saved_rows=config.data['translation_profiles']; config.data['translation_profiles']=[]; tc.refresh_services(); tc.preview()
                check('translation_empty',w,theme,size,snap and theme=='dark')
                config.data['translation_profiles']=saved_rows; tc.refresh_services()
                tc.new_task(); w.show_glossary(); glossary=w.glossary_workspace
                # Fixture cleared/populated through the existing service, never through UI truth copies.
                service.connection.execute('DELETE FROM glossary'); service.connection.commit(); glossary.load()
                glossary.tabs.setCurrentIndex(0); check('glossary_empty',w,theme,size,snap)
                glossary.service.save({'source_term':'勇者','target_term':'Hero','category':'character','note':''}); glossary.refresh_terms()
                check('glossary_populated',w,theme,size,snap)
                glossary.tabs.setCurrentIndex(1); check('characters',w,theme,size,snap and theme=='dark')
                dialogs=[('new_project',NewProjectDialog(w.language,w)),('settings',SettingsDialog(w)),
                    ('font_browser',FontPicker(['Microsoft YaHei','Arial'],'Microsoft YaHei',w,language=w.language,config=config,sample='当前译文，用于字体预览。')),
                    ('provider',ProfileEditor(store,w.language,profile,w)),('import_preview',ImportPreviewDialog(preview,w.language,w)),
                    ('export_options',ExportOptionsDialog(service.path,1,w.language,w)),('about',AboutDialog(w)),
                    ('term_editor',TermEditor(glossary)),('project_styles',ProjectStylesDialog(ProjectStyleService(service.connection),w.language,lambda *a:None,w)),
                    ('mask_editor',MaskDialog(QImage(str(source)),parent=w)),('translation_details',TranslationDetailsDialog(service.connection,block['id'],w.language,w)),
                    ('legacy_translation_range',TranslationRangeDialog(ws)),('legacy_project_translation',ProjectTranslationDialog(service.connection,w.language,w))]
                for name,d in dialogs:
                    d.show(); app.processEvents(); check(name,d,theme,size,snap and (theme=='dark' or name in ('settings','provider','import_preview','export_options','about','font_browser')),inset=True)
                    if name=='settings':
                        for index in range(7): d.navigation.setCurrentRow(index); check('settings_'+str(index),d,theme,size,snap and theme=='dark')
                    if name=='provider': d.advanced.header.setChecked(True); check('provider_advanced',d,theme,size,snap and theme=='dark')
                    d.close(); d.deleteLater()
                for name,icon in (('error',QMessageBox.Icon.Warning),('confirmation',QMessageBox.Icon.Question)):
                    d=QMessageBox(icon,'提示','这是可控的离线验收状态。',QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel,w); d.show(); check(name,d,theme,size,snap and theme=='dark'); d.close(); d.deleteLater()
                d=QInputDialog(w); d.setLabelText('模型 / Model'); d.show(); check('model_prompt',d,theme,size,snap and theme=='dark'); d.close(); d.deleteLater()
                d=QFileDialog(w,'Import'); d.setOption(QFileDialog.Option.DontUseNativeDialog,True); d.show(); check('qt_file_picker',d,theme,size,False); d.close(); d.deleteLater()
                w.show_manga(); ws.right_tabs.setCurrentIndex(0); ws.left_tabs.setCurrentIndex(0)
                if snap:
                    for key,(button,_) in w.workflow_buttons.items():
                        menu=button.menu(); menu.popup(button.mapToGlobal(button.rect().bottomLeft())); app.processEvents(); check('popup_'+key,menu,theme,size,save); menu.hide()
        w.close()
    destination=Path(os.environ.get('LMW_UI_AUDIT_DIR','dev_data/ui-r3')); destination.mkdir(parents=True,exist_ok=True)
    (destination/f'geometry-{scale}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    failures=[r for r in records if r['status']=='FAIL']
    print(json.dumps({'scale':scale,'total':len(records),'PASS':len(records)-len(failures),'FAIL':len(failures),'failures':failures[:12]},ensure_ascii=False))
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
