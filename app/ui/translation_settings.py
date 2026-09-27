"""Translation profile settings and simple project terminology editor."""
from dataclasses import replace
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QComboBox,
    QPushButton, QDialog, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox,
    QLabel, QMessageBox, QPlainTextEdit, QTableWidget, QTableWidgetItem, QTabWidget, QInputDialog)
from app.translation.profiles import ProfileStore, new_profile, TranslationError
from app.translation.providers import provider_for, PRESETS
from app.translation.service import TranslationService
from .workers import Job
from .components import CollapsibleSection, localize_buttons


class ProfileEditor(QDialog):
    def __init__(self, store, language, profile=None, parent=None):
        super().__init__(parent)
        self.store, self.language = store, language
        self.profile = profile or new_profile()
        self.job = None
        tr = language.tr
        self.setWindowTitle(tr("ai.provider_edit"))
        self.resize(520, 420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16,16,16,16)
        form = QFormLayout()
        self.basic_form=form
        outer.addLayout(form)
        self.fields = {}
        for name in ("name", "base_url", "model"):
            field = QLineEdit(str(getattr(self.profile, name)))
            self.fields[name] = field
            form.addRow(tr("ai." + name), field)
        self.kind = QComboBox()
        for kind in ("openai", "ollama", "local_openai"):
            self.kind.addItem(tr("ai.kind_" + kind), kind)
        self.kind.setCurrentIndex(self.kind.findData(self.profile.provider_type))
        form.insertRow(1, tr("ai.provider_type"), self.kind)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(tr("ai.key_keep"))
        form.addRow(tr("ai.api_key"), self.key)
        advanced_body = QWidget()
        advanced_form = QFormLayout(advanced_body)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        for name, lo, hi in (("timeout", 1, 600), ("max_retries", 0, 6), ("max_concurrency", 1, 4)):
            field = QSpinBox()
            field.setRange(lo, hi)
            field.setValue(getattr(self.profile, name))
            self.fields[name] = field
            advanced_form.addRow(tr("ai." + name), field)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0, 2)
        self.temperature.setSingleStep(.1)
        self.temperature.setValue(self.profile.temperature)
        advanced_form.addRow(tr("ai.temperature"), self.temperature)
        self.enabled = QCheckBox(tr("ai.enabled"))
        self.enabled.setChecked(self.profile.enabled)
        advanced_form.addRow(self.enabled)
        self.advanced = CollapsibleSection(tr("ui.advanced_options"), advanced_body)
        outer.addWidget(self.advanced)
        row = QHBoxLayout()
        self.test = QPushButton(tr("ai.test_connection"))
        self.detect = QPushButton(tr("ai.detect_models"))
        row.addWidget(self.test); row.addWidget(self.detect)
        outer.addLayout(row)
        self.health = QLabel()
        self.health.setWordWrap(True)
        outer.addWidget(self.health)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(self.buttons,tr)
        outer.addWidget(self.buttons)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        self.test.clicked.connect(lambda: self.check(False))
        self.detect.clicked.connect(lambda: self.check(True))
        self.kind.currentIndexChanged.connect(self.kind_changed)
        self.key.setEnabled(self.profile.provider_type in ("openai", "local_openai"))
        self.key.setVisible(self.profile.provider_type != "ollama")
        form.labelForField(self.key).setVisible(self.profile.provider_type != "ollama")

    def kind_changed(self):
        kind = self.kind.currentData()
        self.fields["base_url"].setText("http://localhost:11434" if kind == "ollama" else
            "http://localhost:1234/v1" if kind == "local_openai" else "https://api.openai.com/v1")
        self.fields["max_concurrency"].setValue(1 if kind != "openai" else 2)
        self.key.setEnabled(kind in ("openai", "local_openai"))
        self.key.setVisible(kind != "ollama")
        self.basic_form.labelForField(self.key).setVisible(kind != "ollama")

    def value(self):
        values = {name: field.text().strip() if isinstance(field, QLineEdit) else field.value()
                  for name, field in self.fields.items()}
        return replace(self.profile, **values, provider_type=self.kind.currentData(),
                       temperature=self.temperature.value(), enabled=self.enabled.isChecked())

    def save(self):
        try:
            self.store.save(self.value(), self.key.text() or None)
        except TranslationError as exc:
            self.health.setText(self.language.tr("ai.error_" + exc.code))
            return
        self.key.clear()
        self.accept()

    def check(self, detect):
        try:
            profile = self.value()
            if detect and not profile.model:
                profile = replace(profile, model="_detect_")
            profile.validate()
            key = self.key.text() or self.store.key(profile)
            provider = provider_for(replace(profile, timeout=min(profile.timeout, 8), max_retries=0), key)
        except TranslationError as exc:
            self.health.setText(self.language.tr("ai.error_" + exc.code)); return
        def operation(progress, cancel):
            try:
                return provider.detect_models() if detect else provider.test_connection()
            except TranslationError as exc:
                return {"error": exc.code}
            except Exception:
                logging.getLogger(__name__).exception("Provider connection check failed")
                return {"error": "translation_failed"}
        self.test.setEnabled(False); self.detect.setEnabled(False)
        self.buttons.setEnabled(False)
        self.health.setText(self.language.tr("ai.connecting"))
        self.job = Job(operation, self)
        self.job.result.connect(self.checked)
        self.job.finished.connect(self.finished_check)
        self.job.start()

    def checked(self, result):
        if isinstance(result, dict):
            self.health.setText(self.language.tr("ai.error_" + result["error"]))
        elif isinstance(result, list):
            if result:
                choice, ok = QInputDialog.getItem(self, self.language.tr("ai.detect_models"),
                    self.language.tr("ai.model"), result, 0, False)
                if ok: self.fields["model"].setText(choice)
            self.health.setText(self.language.tr("ai.models_found", count=len(result)))
        else:
            self.health.setText(self.language.tr("ai." + result))

    def finished_check(self):
        self.test.setEnabled(True); self.detect.setEnabled(True); self.buttons.setEnabled(True)
        if self.job:
            self.job.deleteLater()
        self.job = None

    def reject(self):
        if self.job and self.job.isRunning():
            return
        super().reject()

    def closeEvent(self, event):
        if self.job and self.job.isRunning(): event.ignore()
        else: super().closeEvent(event)


class TranslationSettings(QWidget):
    def __init__(self, host, parent=None):
        super().__init__(parent);self.host=host;outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        zh=host.language.language=="zh_CN";form=QFormLayout();outer.addLayout(form)
        self.profiles=QComboBox();self.profiles.addItem("未设置" if zh else "Not set",None)
        for p in ProfileStore(host.service.config).list():
            if p.enabled and p.provider_type!="manual":self.profiles.addItem(p.name,p.id)
        self.profiles.setCurrentIndex(max(0,self.profiles.findData(host.service.config.data.get("translation_profile_id"))))
        form.addRow("默认翻译服务" if zh else "Default translation service",self.profiles)
        self.target=QComboBox();self.target.addItems(["简体中文","繁體中文","English","日本語"]);self.target.setCurrentText(host.service.config.data.get("translation_target_language","简体中文"));form.addRow("默认目标语言" if zh else "Default target language",self.target)
        def save():
            host.service.config.data["translation_profile_id"]=self.profiles.currentData();host.service.config.data["translation_target_language"]=self.target.currentText();host.service.config.save()
        self.profiles.currentIndexChanged.connect(save);self.target.currentTextChanged.connect(save)
        for cn,en,tab in (("管理翻译服务","Manage services",2),("打开翻译中心","Open Translation Center",0)):
            button=QPushButton(cn if zh else en);button.setEnabled(host.service.connection is not None)
            def open_center(checked=False,tab=tab):
                if isinstance(self.window(),QDialog):self.window().accept()
                host.show_translation_center();host.translation_center.tabs.setCurrentIndex(tab)
            button.clicked.connect(open_center);outer.addWidget(button)


class ProjectTranslationDialog(QDialog):
    """DEPRECATED: old configuration automation adapter, no ordinary UI entry.

    Earliest removal: 0.7 after callers adopt Glossary/TranslationCenter.
    """
    def __init__(self, db, language, parent=None):
        super().__init__(parent)
        self.service, self.language = TranslationService(db), language
        tr = language.tr
        self.setWindowTitle(tr("ai.project_settings")); self.resize(850, 600)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16,16,16,16)
        form = QFormLayout(); outer.addLayout(form)
        settings = self.service.settings()
        self.target = QLineEdit(settings["target_language"])
        form.addRow(tr("ai.target_language"), self.target)
        self.preset = QComboBox()
        for key in PRESETS: self.preset.addItem(tr("ai.preset_"+key), key)
        self.preset.setCurrentIndex(self.preset.findData(settings["preset"]))
        form.addRow(tr("ai.preset"), self.preset)
        self.context = QSpinBox(); self.context.setRange(0, 10); self.context.setValue(settings["context_pages"])
        self.context_summary = QLabel(tr("ui.context_summary", pages=settings["context_pages"]))
        self.context_summary.setProperty("role", "muted")
        form.addRow(tr("ai.context_pages"), self.context_summary)
        advanced_body = QWidget(); advanced_form = QFormLayout(advanced_body)
        advanced_form.setContentsMargins(0,0,0,0)
        self.context_mode = QComboBox()
        for label,value in (("ui.context_current",0),("ui.context_one",1),("ui.context_two",2),("ui.context_custom",-1)):
            self.context_mode.addItem(tr(label),value)
        self.context_mode.setCurrentIndex(self.context_mode.findData(settings["context_pages"]) if settings["context_pages"] in (0,1,2) else 3)
        advanced_form.addRow(tr("ai.context_pages"),self.context_mode)
        advanced_form.addRow(tr("ui.context_custom"),self.context)
        self.context.setVisible(self.context_mode.currentData()==-1)
        advanced_form.labelForField(self.context).setVisible(self.context_mode.currentData()==-1)
        def change_context():
            value=self.context_mode.currentData()
            if value>=0:self.context.setValue(value)
            self.context.setVisible(value==-1)
            advanced_form.labelForField(self.context).setVisible(value==-1)
            self.context_summary.setText(tr("ui.context_summary",pages=self.context.value()))
        self.context_mode.currentIndexChanged.connect(change_context)
        self.context.valueChanged.connect(lambda: self.context_summary.setText(tr("ui.context_summary",pages=self.context.value())))
        self.instructions = QPlainTextEdit(settings["instructions"]); self.instructions.setMaximumHeight(100)
        advanced_form.addRow(tr("ai.instructions"), self.instructions)
        self.advanced = CollapsibleSection(tr("ui.advanced_options"),advanced_body)
        outer.addWidget(self.advanced)
        tabs = QTabWidget(); outer.addWidget(tabs)
        self.tables = {}
        definitions = {"glossary": ["source_term", "target_term", "note", "case_sensitive", "exact_match"],
                       "character_notes": ["name", "translated_name", "description", "speech_style"]}
        for table, columns in definitions.items():
            panel = QWidget(); layout = QVBoxLayout(panel)
            widget = QTableWidget(0, len(columns)); widget.setHorizontalHeaderLabels([tr("ai."+c) for c in columns])
            self.tables[table] = (widget, columns)
            if table == "glossary":
                for index in (3,4):widget.setColumnHidden(index,True)
                self.advanced.header.toggled.connect(lambda shown,w=widget: [w.setColumnHidden(i,not shown) for i in (3,4)])
            else:
                widget.setColumnHidden(2,True)
                self.advanced.header.toggled.connect(lambda shown,w=widget:w.setColumnHidden(2,not shown))
            widget.horizontalHeader().setStretchLastSection(True)
            for row in self.service.terms(table):
                index = widget.rowCount(); widget.insertRow(index)
                for col, key in enumerate(columns): widget.setItem(index, col, QTableWidgetItem(str(row[key])))
            layout.addWidget(widget)
            row = QHBoxLayout(); add = QPushButton(tr("ai.add_row")); delete = QPushButton(tr("ai.delete_row"))
            add.clicked.connect(lambda checked=False, w=widget: w.insertRow(w.rowCount()))
            delete.clicked.connect(lambda checked=False, w=widget: w.removeRow(w.currentRow()))
            row.addWidget(add); row.addWidget(delete); layout.addLayout(row)
            tabs.addTab(panel, tr("ai."+table))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(buttons,tr)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); outer.addWidget(buttons)

    def save(self):
        values = {}
        for table, (widget, columns) in self.tables.items():
            rows = []
            for r in range(widget.rowCount()):
                row = {key: widget.item(r,c).text().strip() if widget.item(r,c) else "" for c,key in enumerate(columns)}
                if not any(row.values()): continue
                for key in ("case_sensitive", "exact_match"):
                    if key in row: row[key] = row[key].lower() in ("1", "true", "yes") or (key == "exact_match" and row[key] == "")
                rows.append(row)
            values[table] = rows
        try:
            self.service.replace_terms(values["glossary"], values["character_notes"])
            self.service.save_settings({"target_language": self.target.text(), "preset": self.preset.currentData(),
                "context_pages": self.context.value(), "instructions": self.instructions.toPlainText()})
        except TranslationError as exc:
            QMessageBox.warning(self, self.windowTitle(), self.language.tr("ai.error_"+exc.code)); return
        self.accept()
