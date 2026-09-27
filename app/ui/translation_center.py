"""Native in-app batch translation center built on the existing queue/providers."""
import json
import logging
from dataclasses import replace
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,QLabel,QPushButton,
    QComboBox,QLineEdit,QCheckBox,QTabWidget,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,
    QStackedWidget,QScrollArea,QMessageBox,QDialog,QDialogButtonBox,QInputDialog,QPlainTextEdit)
from app.translation.profiles import ProfileStore,TranslationError,new_profile
from app.translation.providers import provider_for,PRESETS
from app.translation.service import TranslationService
from app.translation.telemetry import task_metrics
from app.translation.tasks import create_translation_task
from app.tasks.service import TaskService
from app.ocr.review import TextBlockService
from .translation_settings import ProfileEditor
from .components import CollapsibleSection,localize_buttons,exec_dialog
from .workers import Job

class TranslationCenter(QWidget):
    def __init__(self, host):
        super().__init__();self.host=host;self.ws=host.workspace;self.store=ProfileStore(host.service.config);self.service=None;self.task_id=None;self.check_job=None;self.connections={};self._last=None;self._history_signature=None;self.history_limit=100
        outer=QVBoxLayout(self);outer.setContentsMargins(16,12,16,16);outer.setSpacing(10)
        heading=QHBoxLayout();title=QLabel(self.text("翻译中心","Translation Center"));title.setProperty("role","title");heading.addWidget(title);heading.addStretch()
        self.back=QPushButton(self.text("返回漫画","Back to manga"));self.back.clicked.connect(host.show_manga);heading.addWidget(self.back);outer.addLayout(heading)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        self.task_stack=QStackedWidget();self.tabs.addTab(self.task_stack,self.text("翻译任务","Translation Task"));self.build_setup();self.build_progress();self.build_history();self.build_services()
        self.timer=QTimer(self);self.timer.setInterval(500);self.timer.timeout.connect(self.poll)
        self.tabs.currentChanged.connect(lambda index:self.refresh_history() if index==1 else None)
    def text(self,cn,en):return cn if self.host.language.language=="zh_CN" else en
    def button(self,cn,en,handler):
        b=QPushButton(self.text(cn,en));b.clicked.connect(handler);return b
    def heading(self,layout,cn,en):
        label=QLabel(self.text(cn,en));label.setProperty("role","section");layout.addWidget(label)
    def build_setup(self):
        panel=QWidget();layout=QVBoxLayout(panel);layout.setContentsMargins(16,12,16,16);layout.setSpacing(6)
        container=QWidget();container_layout=QVBoxLayout(container);container_layout.setContentsMargins(0,0,0,0);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(panel);container_layout.addWidget(scroll,1);self.task_stack.addWidget(container)
        self.project_summary=QLabel();self.project_summary.setProperty("role","muted");layout.addWidget(self.project_summary)
        self.heading(layout,"翻译范围","Translation scope");form=QFormLayout();layout.addLayout(form)
        self.scope=QComboBox()
        for key,cn,en in (("block","当前文本","Current text"),("page","当前页","Current page"),("selected","所选页面","Selected pages"),("batch","当前批次","Current batch"),("project","整个项目","Entire project")):self.scope.addItem(self.text(cn,en),key)
        self.scope.setMaximumWidth(650);self.scope.setCurrentIndex(1);form.addRow(self.text("范围","Scope"),self.scope)
        self.selection=QLineEdit();self.selection.setPlaceholderText("1, 3, 5-10");self.selection_label=QLabel(self.text("页面范围","Pages"));form.addRow(self.selection_label,self.selection)
        self.range_summary=QLabel();self.range_summary.setWordWrap(True);layout.addWidget(self.range_summary)
        self.empty=QLabel();self.empty.setWordWrap(True);layout.addWidget(self.empty)
        self.ocr_button=self.button("识别当前页","Recognize current page",self.recognize);layout.addWidget(self.ocr_button,alignment=Qt.AlignmentFlag.AlignLeft)
        self.heading(layout,"翻译服务","Translation service");service_form=QFormLayout();layout.addLayout(service_form)
        self.provider=QComboBox();self.provider.setMaximumWidth(650);service_form.addRow(self.text("服务","Service"),self.provider)
        self.model=QComboBox();self.model.setMaximumWidth(650);service_form.addRow(self.text("模型","Model"),self.model)
        row=QHBoxLayout();self.connection_label=QLabel(self.text("○ 未检测","○ Not checked"));row.addWidget(self.connection_label)
        self.test_button=self.button("测试连接","Test connection",lambda:self.check_connection(False));row.addWidget(self.test_button)
        row.addWidget(self.button("服务配置","Service configuration",lambda:self.tabs.setCurrentIndex(2)));row.addStretch();layout.addLayout(row)
        self.heading(layout,"翻译设置","Translation settings");settings_form=QFormLayout();layout.addLayout(settings_form)
        self.target=QComboBox();self.target.setMaximumWidth(320);self.target.setEditable(True);self.target.addItems(["简体中文","繁體中文","English","日本語"]);settings_form.addRow(self.text("目标语言","Target language"),self.target)
        self.preset=QComboBox();self.preset.setMaximumWidth(320)
        for key in PRESETS:self.preset.addItem(self.host.language.tr("ai.preset_"+key),key)
        settings_form.addRow(self.text("风格","Style"),self.preset)
        self.context=QComboBox();self.context.setMaximumWidth(320)
        for n in (0,1,2):self.context.addItem(self.text("仅当前页" if not n else f"前后 {n} 页","Current page only" if not n else f"±{n} pages"),n)
        settings_form.addRow(self.text("上下文","Context"),self.context)
        self.glossary=QCheckBox();self.characters=QCheckBox();settings_form.addRow(self.glossary);settings_form.addRow(self.characters)
        layout.addWidget(self.button("查看项目术语库","View project glossary",self.host.show_glossary),alignment=Qt.AlignmentFlag.AlignLeft)
        self.drafts=QCheckBox(self.host.language.tr("ai.include_drafts"));layout.addWidget(self.drafts)
        advanced=QWidget();af=QVBoxLayout(advanced);af.setContentsMargins(0,0,0,0);self.overwrite=QCheckBox(self.host.language.tr("ai.overwrite_protected"));af.addWidget(self.overwrite)
        self.instructions=QPlainTextEdit();self.instructions.setMaximumHeight(70);self.instructions.setPlaceholderText(self.text("项目自定义说明","Project instructions"));af.addWidget(self.instructions)
        self.advanced=CollapsibleSection(self.text("高级任务选项","Advanced task options"),advanced);layout.addWidget(self.advanced)
        self.rule_summary=QLabel();self.rule_summary.setWordWrap(True)
        self.privacy=QLabel();self.privacy.setWordWrap(True);self.privacy.setProperty("role","muted")
        layout.addStretch();footer=QHBoxLayout();self.start_button=self.button("开始翻译","Start translation",self.preflight);self.start_button.setProperty("variant","primary");summary_column=QVBoxLayout();summary_column.addWidget(self.rule_summary);summary_column.addWidget(self.privacy);footer.addLayout(summary_column,1);footer.addWidget(self.start_button,alignment=Qt.AlignmentFlag.AlignBottom);footer.setContentsMargins(16,8,16,12);container_layout.addLayout(footer)
        for sig in (self.scope.currentIndexChanged,self.selection.textChanged,self.provider.currentIndexChanged,self.target.currentTextChanged,self.preset.currentIndexChanged,self.context.currentIndexChanged,self.glossary.toggled,self.characters.toggled,self.drafts.toggled,self.overwrite.toggled):sig.connect(self.preview)
    def build_progress(self):
        panel=QWidget();layout=QVBoxLayout(panel);layout.setContentsMargins(16,16,16,16);layout.setSpacing(12);self.task_stack.addWidget(panel)
        self.progress_title=QLabel();self.progress_title.setProperty("role","title");layout.addWidget(self.progress_title)
        self.progress_page=QLabel();layout.addWidget(self.progress_page)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setTextVisible(True);self.progress.setMinimumHeight(24);layout.addWidget(self.progress)
        self.grid=QGridLayout();self.metrics={}
        for n,(key,cn,en) in enumerate((("completed","已完成","Completed"),("success","成功","Success"),("failed","失败","Failed"),("requests","请求","Requests"),("time","用时","Elapsed"),("skipped","跳过","Skipped"))):
            self.grid.addWidget(QLabel(self.text(cn,en)),n//3*2,n%3);label=QLabel("—");label.setProperty("role","section");self.grid.addWidget(label,n//3*2+1,n%3);self.metrics[key]=label
        layout.addLayout(self.grid);self.tokens=QLabel();layout.addWidget(self.tokens);layout.addWidget(QLabel(self.text("费用估算：未配置","Cost estimate: not configured")))
        self.current=QLabel();self.current.setWordWrap(True);layout.addWidget(self.current)
        self.failures=QTableWidget(0,4);self.failures.setHorizontalHeaderLabels([self.text("页面","Page"),self.text("文本块","Blocks"),self.text("问题 · 双击定位","Error · double-click to locate"),self.text("操作","Action")]);self.failures.horizontalHeader().setStretchLastSection(True);self.failures.setMaximumHeight(180);self.failures.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.failures.cellDoubleClicked.connect(self.locate_failure);layout.addWidget(self.failures,1)
        self.failures.horizontalHeader().setStretchLastSection(False)
        self.failures.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.failures.setColumnWidth(3,100)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(130);layout.addWidget(CollapsibleSection(self.text("详细信息","Details"),self.details))
        layout.addStretch(1)
        controls=QHBoxLayout();self.pause_button=self.button("暂停","Pause",lambda:self.control("paused"));self.resume_button=self.button("继续","Resume",lambda:self.resume(False));self.cancel_button=self.button("取消任务","Cancel task",lambda:self.control("cancel_requested"));self.retry_button=self.button("重试失败项","Retry failed items",lambda:self.resume(True));self.review_button=self.button("查看 AI 初译","Review AI drafts",self.review);self.new_button=self.button("新任务","New task",self.new_task)
        for b in (self.pause_button,self.resume_button,self.cancel_button,self.retry_button,self.review_button,self.new_button):controls.addWidget(b)
        controls.addStretch();layout.addLayout(controls)
    def build_history(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(12,12,12,12);layout.addWidget(QLabel(self.text("双击任务查看结果或继续。","Double-click a task to inspect or resume.")))
        self.history=QTableWidget(0,6);self.history.setHorizontalHeaderLabels([self.text(c,e) for c,e in zip(("时间","范围","模型","成功 / 失败","Token","状态"),("Time","Scope","Model","Success / Failed","Tokens","Status"))]);self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.history.horizontalHeader().setStretchLastSection(True);self.history.cellDoubleClicked.connect(self.open_history);layout.addWidget(self.history,1);self.tabs.addTab(page,self.text("历史任务","History"))
    def build_services(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(12,12,12,12);row=QHBoxLayout()
        for cn,en,handler in (("＋ 添加服务","+ Add service",self.add_service),("编辑","Edit",self.edit_service),("检测服务","Detect service",lambda:self.check_connection(False,True)),("刷新模型","Refresh models",lambda:self.check_connection(True,True))):row.addWidget(self.button(cn,en,handler))
        row.addStretch();layout.addLayout(row);self.services=QTableWidget(0,4);self.services.setHorizontalHeaderLabels([self.text(c,e) for c,e in zip(("名称","类型","模型","状态"),("Name","Type","Model","Status"))]);self.services.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.services.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.services.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.services.horizontalHeader().setStretchLastSection(True);self.services.cellDoubleClicked.connect(lambda *_:self.edit_service());layout.addWidget(self.services,1)
        self.service_hint=QLabel(self.text("还没有翻译服务。添加云端 API 或已安装的本地模型服务。","Add a cloud API or an existing local model server."));self.service_hint.setWordWrap(True);layout.addWidget(self.service_hint);self.tabs.addTab(page,self.text("翻译服务","Services"))
    def showEvent(self,event):
        super().showEvent(event)
        if self.service:self.timer.start()
    def hideEvent(self,event):
        # Task workers keep running; only the hidden view's status polling stops.
        if hasattr(self,'timer'):self.timer.stop()
        super().hideEvent(event)
    def load(self,scope=None):
        if not self.host.service.connection:return
        self.service=TranslationService(self.host.service.connection);settings=self.service.settings()
        for field in (self.target,self.preset,self.context,self.glossary,self.characters):field.blockSignals(True)
        self.target.setCurrentText("简体中文" if self.host.language.language=="zh_CN" and settings["target_language"]=="Simplified Chinese" else settings["target_language"]);self.preset.setCurrentIndex(self.preset.findData(settings["preset"]))
        if self.context.findData(settings["context_pages"])<0:self.context.addItem(f"±{settings['context_pages']}",settings["context_pages"])
        self.context.setCurrentIndex(self.context.findData(settings["context_pages"]));self.glossary.setChecked(settings["glossary_enabled"]);self.characters.setChecked(settings["characters_enabled"]);self.instructions.setPlainText(settings["instructions"])
        for field in (self.target,self.preset,self.context,self.glossary,self.characters):field.blockSignals(False)
        self.refresh_services()
        if self.tabs.currentIndex()==1:self.refresh_history()
        if scope:self.scope.setCurrentIndex(self.scope.findData(scope));self.new_task()
        elif self.task_id and self.host.service.connection.execute("SELECT 1 FROM tasks WHERE id=?",(self.task_id,)).fetchone():self.task_stack.setCurrentIndex(1);self.poll()
        else:self.task_id=None;self.task_stack.setCurrentIndex(0)
        self.preview();self.timer.start()
    def options(self):
        from .translation_scope import options
        return options(self.ws,self.scope.currentData(),self.drafts.isChecked(),self.overwrite.isChecked())
    def page_ids(self):
        from .translation_scope import page_ids
        return page_ids(self.ws,self.scope.currentData(),self.selection.text())
    def preview(self,*args):
        if not self.service:return
        selected=self.scope.currentData()=="selected";self.selection.setVisible(selected);self.selection_label.setVisible(selected)
        self.model.clear();pid=self.provider.currentData();profile=next((p for p in self.store.list() if p.id==pid),None)
        if profile:self.model.addItem(profile.model)
        self.connection_label.setText(self.connections.get(pid,self.text("○ 未检测","○ Not checked")))
        terms=len(self.service.terms("glossary"));chars=len(self.service.terms("character_notes"));self.glossary.setText(self.text(f"使用术语库 · {terms} 条",f"Use glossary · {terms} terms"));self.characters.setText(self.text(f"人物说明 · {chars} 人",f"Character notes · {chars}"))
        self.project_summary.setText(self.text(f"当前项目 · {len(self.ws.model.pages)} 页",f"Current project · {len(self.ws.model.pages)} pages"))
        try:
            ids=self.page_ids();counts=self.service.preview(ids,self.options());self.range_summary.setText(self.text(f"{len(ids)} 页 · 实际翻译 {counts['blocks']} 个文本块",f"{len(ids)} pages · {counts['blocks']} eligible blocks"));eligible=counts["blocks"]>0
        except TranslationError as e:eligible=False;self.range_summary.setText(self.host.language.tr("ai.error_"+e.code))
        self.empty.setText(self.text("还没有翻译服务，请在“翻译服务”中添加。","No service configured. Add one in Services.") if not profile else self.text("当前范围没有可翻译的 OCR 文本，或内容已受保护。","No eligible OCR text, or translations are protected.") if not eligible else "")
        self.empty.setVisible(bool(self.empty.text()))
        self.ocr_button.setVisible(not eligible and bool(self.ws.current_id));self.start_button.setEnabled(bool(profile and eligible and not self.ws.jobs and not self.check_job))
        self.privacy.setText(self.text("本地模型 · 数据不发送至配置之外的服务器。","Local model · Data goes only to your configured server.") if profile and profile.local else self.text("将向你配置的第三方服务发送 OCR 文本。","OCR text will be sent to your configured third-party service."))
        self.rule_summary.setText(self.text(f"原文 → {self.target.currentText()} · {self.preset.currentText()}\n参考前后 {self.context.currentData()} 页 · 使用 {terms if self.glossary.isChecked() else 0} 条术语\n"+("允许覆盖人工修改和已审核内容" if self.overwrite.isChecked() else "跳过已人工修改和已审核内容"),f"Source → {self.target.currentText()} · {self.preset.currentText()}\n±{self.context.currentData()} context pages · {terms if self.glossary.isChecked() else 0} terms\n"+("Overwrite protected translations" if self.overwrite.isChecked() else "Skip human-edited and reviewed translations")))
    def recognize(self):self.host.show_manga();self.ws.ocr_current_page()
    def refresh_services(self):
        selected=self.provider.currentData() or (self.service.settings()["provider_profile_id"] if self.service else None) or self.host.service.config.data.get("translation_profile_id");self.provider.blockSignals(True);self.provider.clear();profiles=[p for p in self.store.list() if p.provider_type!="manual"]
        self.services.setRowCount(len(profiles))
        for n,p in enumerate(profiles):
            if p.enabled:self.provider.addItem(p.name,p.id)
            for col,value in enumerate((p.name,p.provider_type,p.model,self.connections.get(p.id,self.text("未检测","Not checked")) if p.enabled else self.text("已停用","Disabled"))):item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,p.id);self.services.setItem(n,col,item)
        index=self.provider.findData(selected);self.provider.setCurrentIndex(index if index>=0 else 0);self.provider.blockSignals(False);self.service_hint.setVisible(not profiles);self.preview()
    def add_service(self):
        choice,ok=QInputDialog.getItem(self,self.text("添加服务","Add service"),self.text("服务类型","Service type"),[self.text("云端 API","Cloud API"),"Ollama","LM Studio / Local OpenAI-compatible"],0,False)
        if not ok:return
        kind="openai" if choice==self.text("云端 API","Cloud API") else "ollama" if choice=="Ollama" else "local_openai"
        dialog=ProfileEditor(self.store,self.host.language,new_profile(kind),self)
        if exec_dialog(dialog):self.refresh_services();self.provider.setCurrentIndex(self.provider.findData(dialog.profile.id))
    def service_id(self):
        row=self.services.currentRow();return self.services.item(row,0).data(Qt.ItemDataRole.UserRole) if row>=0 else self.provider.currentData()
    def edit_service(self):
        pid=self.service_id()
        if not pid:return
        dialog=ProfileEditor(self.store,self.host.language,self.store.get(pid,enabled_only=False),self)
        if exec_dialog(dialog):self.connections.pop(pid,None);self.refresh_services()
    def check_connection(self,detect=False,from_services=False,after=None):
        if self.check_job:return
        pid=self.service_id() if from_services else self.provider.currentData()
        if not pid:return
        try:
            profile=self.store.get(pid);key=self.store.key(profile)
            if profile.provider_type=="openai" and not key:raise TranslationError("authentication")
            provider=provider_for(replace(profile,timeout=min(profile.timeout,8),max_retries=0),key)
        except TranslationError as e:self.connection_label.setText(self.error(e.code));return
        def operation(progress,cancel):
            try:return {"models":provider.detect_models()} if detect else {"status":provider.test_connection()}
            except TranslationError as e:return {"error":e.code}
            except Exception:
                logging.getLogger(__name__).exception("Translation service check failed")
                return {"error":"translation_failed"}
        self.connection_label.setText(self.text("正在检测服务…","Checking service…"));self.test_button.setEnabled(False);self.start_button.setEnabled(False)
        self.check_job=Job(operation,self)
        def result(data):
            connected=data.get("status")=="connected";self.connections[pid]=self.text("● 已连接","● Connected") if connected else self.error(data.get("error",data.get("status","model_not_found")))
            if "models" in data:
                models=data["models"]
                if models:
                    model,ok=QInputDialog.getItem(self,self.text("选择模型","Choose model"),self.text("模型","Model"),models,0,False)
                    if ok:self.store.save(replace(profile,model=model));self.connections.pop(pid,None)
            self.refresh_services()
            if connected and after:QTimer.singleShot(0,after)
        self.check_job.result.connect(result)
        def finished():
            job=self.check_job;self.check_job=None
            if job:job.deleteLater()
            self.test_button.setEnabled(True);self.preview()
        self.check_job.finished.connect(finished);self.check_job.start()
    def error(self,code):
        if code=="authentication":return self.text("此服务缺少 API Key 或认证失败，请配置服务。","API key missing or authentication failed. Configure the service.")
        if code=="server_not_running":return self.text("无法连接服务，请先启动本地模型服务或检查地址。","Cannot connect. Start your local server or check its address.")
        key="ai.error_"+code
        message=self.host.language.tr(key)
        return self.host.language.tr("ai.error_translation_failed") if message==key else message
    def preflight(self):
        if self.ws.jobs:return
        self.ws._save_translation_debounced();self.check_connection(after=self.confirm_start)
    def protected_counts(self,ids):
        manual=reviewed=0;review=TextBlockService(self.host.service.connection)
        for pid in ids:
            for b in review.for_page(pid):
                if self.scope.currentData()=="block" and b["id"]!=self.ws.selected_block:continue
                t=review.translation(b["id"])
                if not b["source_text"].strip() or not t or not t["text"].strip():continue
                if t["status"]=="reviewed":reviewed+=1
                elif t["status"]!="ai_draft":manual+=1
        return (0,0) if self.overwrite.isChecked() else (manual,reviewed)
    def confirm_start(self):
        if self.ws.jobs:return
        try:
            profile=self.store.get(self.provider.currentData());ids=self.page_ids();counts=self.service.preview(ids,self.options());manual,reviewed=self.protected_counts(ids)
            if not counts["blocks"]:return
            dialog=QDialog(self);dialog.setWindowTitle(self.text("准备翻译","Translation preflight"));layout=QVBoxLayout(dialog);layout.setContentsMargins(16,16,16,16)
            label=QLabel(self.text(f"{len(ids)} 页 · {counts['blocks']+manual+reviewed} 个文本块\n跳过 {manual} 个已人工修改、{reviewed} 个已审核\n实际翻译 {counts['blocks']} 个\n服务：{profile.name} · 模型：{profile.model}",f"{len(ids)} pages · {counts['blocks']+manual+reviewed} blocks\nSkip {manual} human-edited, {reviewed} reviewed\nTranslate {counts['blocks']} blocks\n{profile.name} · {profile.model}"));label.setWordWrap(True);layout.addWidget(label)
            from app.translation.glossary import GlossaryService
            conflicts=len(GlossaryService(self.host.service.connection).conflicts())
            layout.addWidget(QLabel(self.text(f"术语 {len(self.service.terms('glossary')) if self.glossary.isChecked() else 0} 条 · 冲突 {conflicts} · 人物 {len(self.service.terms('character_notes')) if self.characters.isChecked() else 0} 人",f"Glossary {len(self.service.terms('glossary')) if self.glossary.isChecked() else 0} · Conflicts {conflicts} · Characters {len(self.service.terms('character_notes')) if self.characters.isChecked() else 0}")))
            if not profile.local:layout.addWidget(QLabel(self.privacy.text()))
            if self.overwrite.isChecked():layout.addWidget(QLabel(self.host.language.tr("ai.overwrite_confirm")))
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);localize_buttons(buttons,self.host.language.tr);buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.text("开始","Start"));buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            if not exec_dialog(dialog):return
            if not self.store.consented(profile):self.store.consent(profile)
            settings={"target_language":self.target.currentText(),"preset":self.preset.currentData(),"context_pages":self.context.currentData(),"glossary_enabled":self.glossary.isChecked(),"characters_enabled":self.characters.isChecked(),"instructions":self.instructions.toPlainText(),"provider_profile_id":profile.id};self.service.save_settings(settings)
            options={**self.options(),"scope":self.scope.currentData(),"target_blocks":counts["blocks"],"skipped_manual":manual,"skipped_reviewed":reviewed,"provider":profile.provider_type,"model":profile.model,"settings":settings}
            targets=[pid for pid in ids if self.service.prepare(pid,options,context=False)[1]];self.task_id=create_translation_task(self.host.service.connection,targets,profile.id,options);self.task_stack.setCurrentIndex(1)
            from .ai_translation import start_task
            start_task(self.ws,self.task_id);self._last=None;self.poll()
        except TranslationError as e:QMessageBox.warning(self,self.text("无法开始","Cannot start"),self.error(e.code))
    def control(self,status):
        if not self.task_id:return
        if status=="cancel_requested" and not self.ws.jobs:status="cancelled"
        TaskService(self.host.service.connection).set_status(self.task_id,status);self.poll()
    def resume(self,retry,page_id=None):
        if not self.task_id or self.ws.jobs:return
        try:
            row=self.host.service.connection.execute("SELECT options_json FROM tasks WHERE id=?",(self.task_id,)).fetchone();profile=self.store.get(json.loads(row[0])["provider_profile_id"])
            if not self.store.consented(profile):
                if QMessageBox.question(self,self.text("第三方服务","Third-party service"),self.host.language.tr("ai.cloud_consent"))!=QMessageBox.StandardButton.Yes:return
                self.store.consent(profile)
            from .ai_translation import start_task
            start_task(self.ws,self.task_id,retry,page_id);self._last=None;self.poll()
        except TranslationError as e:QMessageBox.warning(self,self.text("无法继续","Cannot resume"),self.error(e.code))
    def review(self):
        self.host.show_manga();self.ws.left_tabs.setCurrentIndex(1);self.ws.ocr_filter.setCurrentIndex(6);self.ws.ai_next_draft()
    def new_task(self):
        if self.ws.jobs:return
        self.task_id=None;self._last=None;self.task_stack.setCurrentIndex(0);self.preview()
    def poll(self):
        if not self.isVisible() or not self.host.service.connection:return
        if self.tabs.currentIndex()==1:self.refresh_history()
        if not self.task_id:return
        m=task_metrics(self.host.service.connection,self.task_id);state=m["status"];opts=m["options"];total=m["blocks"];done=m["success"]+m["failed"]
        self.progress_title.setText(self.text({"running":"正在翻译","paused":"已暂停","cancel_requested":"正在取消","cancelled":"已取消","completed":"翻译完成","failed":"翻译完成 · 有失败项","interrupted":"任务已中断","pending":"准备翻译"}.get(state,state),state.title()))
        self.progress.setValue(round(done/max(1,total)*100));current=m["current"];pages="、".join(r["page_uid"] for r in current)
        processed=sum(r["status"] in ("completed","failed") for r in m["pages"])
        self.progress_page.setText(self.text(f"已处理 {processed} / {m['total_units']} 页 · 当前：{pages or '—'}",f"Processed {processed} / {m['total_units']} pages · Current: {pages or '—'}"))
        if state=="paused" and current:self.progress_title.setText(self.text("正在暂停 · 等待当前请求完成","Pausing · Waiting for current requests"))
        data={"completed":f"{done} / {total}","success":str(m["success"]),"failed":str(m["failed"]),"requests":str(m["request_count"]),"time":f"{int(m['elapsed'])//60:02d}:{int(m['elapsed'])%60:02d}","skipped":str(opts.get("skipped_manual",0)+opts.get("skipped_reviewed",0))}
        for k,v in data.items():self.metrics[k].setText(v)
        signature=(state,m["completed_units"],len(m["requests"]),tuple(r["id"] for r in current),bool(self.ws.jobs))
        if signature==self._last:return
        self._last=signature
        usage=m["usage"];values=usage["values"]
        if all(v is None for v in values.values()):self.tokens.setText(self.text("Token：服务未提供统计","Token: service did not provide usage"))
        else:
            fmt=lambda value:f"{value:,}" if value is not None else self.text("不可用","Unavailable")
            self.tokens.setText(self.text("输入 ","Input ")+fmt(values["prompt_tokens"])+self.text("   输出 ","   Output ")+fmt(values["completion_tokens"])+self.text("   总计 ","   Total ")+fmt(values["total_tokens"])+(self.text(" · 部分统计"," · Partial usage") if usage["partial"] else ""))
        block_count=sum(len(self.service.prepare(r["page_id"],opts,context=False)[1]) for r in current)
        self.current.setText(self.text(f"当前请求：{block_count} 个文本块 · {opts.get('provider','—')} · {opts.get('model','—')}\n"+("等待响应…" if current else ""),f"Current requests: {block_count} blocks · {opts.get('provider','—')} · {opts.get('model','—')}\n"+("Waiting for response…" if current else "")))
        failure=[r for r in m["pages"] if r["status"]=="failed"];self.failures.setRowCount(len(failure));latest={r["item_id"]:r for r in m["requests"]}
        for n,r in enumerate(failure):
            for col,value in enumerate((r["page_uid"],str(latest.get(r["id"],{}).get("block_count","—")),self.error(r["last_error"] or "translation_failed"))):item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,r["page_id"]);self.failures.setItem(n,col,item)
            retry=self.button("重试","Retry",lambda checked=False,pid=r["page_id"]:self.resume(True,pid));retry.setEnabled(not self.ws.jobs and state=="failed");self.failures.setCellWidget(n,3,retry)
        self.failures.setVisible(bool(failure));self.details.setPlainText("\n".join(f"{r['created_at']} · {r['model']} · {r['status']} · {r['duration_ms']} ms · {r['request_count']} request(s)" for r in m["requests"][-20:]))
        busy=bool(self.ws.jobs);self.pause_button.setVisible(state=="running");self.resume_button.setVisible(state in ("paused","interrupted","pending"));self.resume_button.setEnabled(not busy);self.cancel_button.setVisible(state in ("running","paused","interrupted","pending"));self.retry_button.setVisible(bool(failure) and state=="failed");self.retry_button.setEnabled(not busy);self.review_button.setVisible(m["success"]>0);self.new_button.setEnabled(not busy)
    def locate_failure(self,row,col):
        pid=self.failures.item(row,0).data(Qt.ItemDataRole.UserRole);self.host.show_manga()
        for n,p in enumerate(self.ws.model.pages):
            if p["id"]==pid:self.ws.select_page(n);break
    def refresh_history(self):
        # Fetch one extra row to offer older records without materializing all history.
        if not self.host.service.connection:return
        rows=self.host.service.connection.execute("SELECT id,status,completed_units,updated_at FROM tasks WHERE kind='AI_TRANSLATION' ORDER BY created_at DESC,rowid DESC LIMIT ?",(self.history_limit+1,)).fetchall()
        more=len(rows)>self.history_limit;rows=rows[:self.history_limit]
        if not hasattr(self,'history_more'):
            self.history_more=self.button("加载更早任务","Load older tasks",self.load_older_history)
            self.history.parentWidget().layout().addWidget(self.history_more,alignment=Qt.AlignmentFlag.AlignRight)
        self.history_more.setVisible(more)
        signature=tuple(tuple(r) for r in rows)
        if signature==self._history_signature:return
        self._history_signature=signature;self.history.setRowCount(len(rows))
        for n,row in enumerate(rows):
            m=task_metrics(self.host.service.connection,row[0]);opts=m["options"];tokens=m["usage"]["values"]["total_tokens"];values=(m["created_at"][:16].replace("T"," "),opts.get("scope","—"),opts.get("model","—"),f"{m['success']} / {m['failed']}",str(tokens) if tokens is not None else self.text("不可用","Unavailable"),self.host.language.tr("ai.task_"+m["status"]))
            for col,value in enumerate(values):item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row[0]);self.history.setItem(n,col,item)
    def load_older_history(self):
        # Grow only on explicit request; startup and the task setup page never materialize all history.
        self.history_limit+=100
        self.refresh_history()
    def open_history(self,row,col):self.task_id=self.history.item(row,0).data(Qt.ItemDataRole.UserRole);self.task_stack.setCurrentIndex(1);self.tabs.setCurrentIndex(0);self.poll()
