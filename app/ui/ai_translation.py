"""Page-range preview, persistent queue controls and review in the manga workspace."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, QCheckBox,
    QLineEdit, QLabel, QPushButton, QMessageBox, QDialogButtonBox)
from PySide6.QtCore import QTimer, Qt
from app.translation.profiles import ProfileStore, TranslationError
from app.translation.service import TranslationService
from app.translation.tasks import create_translation_task, run_translation_task
from .translation_settings import ProjectTranslationDialog
from .components import localize_buttons


class TranslationRangeDialog(QDialog):
    """DEPRECATED: compatibility for old automation/tests; no main UI entry.

    Earliest removal: 0.7 after compatibility callers migrate to TranslationCenter.
    """
    def __init__(self, workspace, single=False, regenerate=False):
        super().__init__(workspace)
        self.ws = workspace
        self.store = ProfileStore(workspace.config)
        self.service = TranslationService(workspace.pages_service.connection)
        self.setWindowTitle(workspace.language.tr("ai.translate"))
        self.resize(520, 340)
        tr = workspace.language.tr
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16)
        form = QFormLayout(); outer.addLayout(form)
        self.provider = QComboBox()
        mode = workspace.config.data.get("translation_mode", "manual")
        for p in self.store.list():
            if p.enabled and p.provider_type != "manual" and ((p.local and mode == "local") or (not p.local and mode == "cloud")):
                self.provider.addItem(p.name, p.id)
        selected = self.service.settings()["provider_profile_id"] or workspace.config.data.get("translation_profile_id")
        if self.provider.findData(selected) >= 0: self.provider.setCurrentIndex(self.provider.findData(selected))
        form.addRow(tr("ai.provider"), self.provider)
        self.configure_button = QPushButton(tr("ui.configure_translation"))
        self.configure_button.clicked.connect(self.configure)
        outer.addWidget(self.configure_button)
        self.scope = QComboBox()
        for key in ("block", "page", "batch", "selected", "project"):
            self.scope.addItem(tr("ai.scope_"+key), key)
        self.scope.setCurrentIndex(0 if single else 1)
        form.addRow(tr("ai.range"), self.scope)
        self.selection = QLineEdit(); self.selection.setPlaceholderText("1, 3, 5-10")
        self.selection_label = QLabel(tr("ai.selected_pages"))
        form.addRow(self.selection_label, self.selection)
        self.drafts = QCheckBox(tr("ai.include_drafts")); self.drafts.setChecked(regenerate)
        self.overwrite = QCheckBox(tr("ai.overwrite_protected"))
        outer.addWidget(self.drafts); outer.addWidget(self.overwrite)
        self.overwrite.setVisible(not workspace.model.simple_mode)
        self.scope_hint = QLabel(workspace.language.tr("ui.scope_skip"))
        self.scope_hint.setProperty("role", "muted");self.scope_hint.setWordWrap(True)
        outer.addWidget(self.scope_hint)
        self.preview_label = QLabel(); self.preview_label.setWordWrap(True); outer.addWidget(self.preview_label)
        settings = QPushButton(tr("ai.project_settings")); outer.addWidget(settings)
        settings.clicked.connect(self.project_settings)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(self.buttons,tr)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ai.start"))
        self.buttons.accepted.connect(self.start); self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        self.scope.currentIndexChanged.connect(self.preview)
        self.selection.textChanged.connect(self.preview)
        self.drafts.toggled.connect(self.preview); self.overwrite.toggled.connect(self.preview)
        self.provider.currentIndexChanged.connect(self.preview)
        self.preview()

    def configure(self):
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.ws.window())
        dialog.navigation.setCurrentRow(3)
        dialog.exec()
        self.provider.blockSignals(True)
        self.provider.clear()
        mode = self.ws.config.data.get("translation_mode","manual")
        for profile in self.store.list():
            if profile.enabled and ((mode=="local" and profile.local) or (mode=="cloud" and profile.provider_type=="openai")):
                self.provider.addItem(profile.name,profile.id)
        selected=self.ws.config.data.get("translation_profile_id")
        if self.provider.findData(selected)>=0:self.provider.setCurrentIndex(self.provider.findData(selected))
        self.provider.blockSignals(False)
        self.preview()

    def options(self):
        from .translation_scope import options
        return options(self.ws,self.scope.currentData(),self.drafts.isChecked(),self.overwrite.isChecked())

    def page_ids(self):
        from .translation_scope import page_ids
        return page_ids(self.ws,self.scope.currentData(),self.selection.text())

    def preview(self):
        self.selection.setVisible(self.scope.currentData() == "selected")
        self.selection_label.setVisible(self.scope.currentData() == "selected")
        try:
            counts = self.service.preview(self.page_ids(), self.options())
            self.preview_label.setText(self.ws.language.tr("ai.preview", **counts))
            enabled = counts["blocks"] > 0 and self.provider.currentData() is not None
            if not self.provider.currentData(): self.preview_label.setText(self.ws.language.tr("ai.choose_provider"))
        except TranslationError as exc:
            enabled = False; self.preview_label.setText(self.ws.language.tr("ai.error_"+exc.code))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(enabled)

    def project_settings(self):
        ProjectTranslationDialog(self.ws.pages_service.connection, self.ws.language, self).exec()
        self.preview()

    def start(self):
        profile = self.store.get(self.provider.currentData())
        if not self.store.consented(profile):
            answer = QMessageBox.question(self, self.windowTitle(), self.ws.language.tr("ai.cloud_consent"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: return
            self.store.consent(profile)
        options = self.options()
        if options["overwrite_protected"]:
            answer = QMessageBox.question(self, self.windowTitle(), self.ws.language.tr("ai.overwrite_confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: return
        self.service.save_settings({"provider_profile_id": profile.id})
        targets = [pid for pid in self.page_ids() if self.service.prepare(pid, options, context=False)[1]]
        task_id = create_translation_task(self.ws.pages_service.connection, targets, profile.id, options)
        self.accept()
        start_task(self.ws, task_id)


def open_translation(workspace, single=False, regenerate=False):
    if not workspace.pages_service:return
    workspace.window().show_translation_center("block" if single else "page")
    workspace.window().translation_center.drafts.setChecked(regenerate)


def start_task(workspace, task_id, retry=False, retry_page_id=None):
    store = ProfileStore(workspace.config)
    project = workspace.project
    def operation(progress, cancel):
        try:
            return run_translation_task(project, store, task_id, progress, cancel, retry, retry_page_id=retry_page_id)
        except TranslationError as exc:
            return {"error": exc.code}
    def finished(result):
        workspace.refresh_ai_tasks()
        if "error" in result:
            QMessageBox.warning(workspace, workspace.language.tr("ai.translate"), workspace.language.tr("ai.error_"+result["error"]))
        else:
            workspace.cache.clear()
            if workspace.current_row >= 0: workspace.reload_pages(workspace.current_id)
            workspace.status_changed.emit(workspace.language.tr("ai.finished", done=result["completed"],
                total=result["total"], failed=result["items"].get("failed",0), status=workspace.language.tr("ai.task_"+result["status"]),
                tokens=result.get("usage",{}).get("total_tokens",workspace.language.tr("ui.not_available"))))
    workspace.run_job(operation, finished, "ai.translate")
    workspace.ai_task_id = task_id
    workspace.ai_job = workspace.jobs[-1]
    workspace.ai_job.finished.connect(lambda: setattr(workspace, "ai_job", None))
    workspace.refresh_ai_tasks()


def pause(workspace):
    job = getattr(workspace, "ai_job", None)
    if job: job.cancel.set()


def resume(workspace, retry=False):
    if not workspace.pages_service or workspace.jobs: return
    statuses = "('failed')" if retry else "('paused','interrupted','pending')"
    selected = workspace.ai_task_list.currentItem()
    if selected:
        task_id = selected.data(Qt.ItemDataRole.UserRole)
        row = workspace.pages_service.connection.execute("SELECT * FROM tasks WHERE id=? AND kind='AI_TRANSLATION' AND status IN " + statuses, (task_id,)).fetchone()
    else:
        row = workspace.pages_service.connection.execute("SELECT * FROM tasks WHERE kind='AI_TRANSLATION' AND status IN " +
            statuses + " ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        QMessageBox.information(workspace, workspace.language.tr("ai.translate"), workspace.language.tr("ai.no_task"))
        return
    import json
    try:
        store = ProfileStore(workspace.config)
        profile = store.get(json.loads(row["options_json"])["provider_profile_id"])
        if not store.consented(profile):
            answer = QMessageBox.question(workspace, workspace.language.tr("ai.translate"), workspace.language.tr("ai.cloud_consent"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: return
            store.consent(profile)
    except TranslationError as exc:
        QMessageBox.warning(workspace, workspace.language.tr("ai.translate"), workspace.language.tr("ai.error_"+exc.code))
        return
    workspace._save_translation_debounced()
    start_task(workspace, row["id"], retry)


def reviewed(workspace):
    if not workspace.selected_block: return
    workspace._save_translation_debounced()
    try:
        TranslationService(workspace.pages_service.connection).mark_reviewed(workspace.selected_block)
        workspace.select_block(workspace.selected_block)
        workspace._refresh_ocr_list()
    except TranslationError as exc:
        QMessageBox.warning(workspace, workspace.language.tr("ai.reviewed"), workspace.language.tr("ai.error_"+exc.code))


def next_draft(workspace):
    if not workspace.pages_service: return
    rows = workspace.pages_service.connection.execute("""SELECT p.id page_id,b.id block_id FROM translations t
        JOIN text_blocks b ON b.id=t.text_block_id JOIN pages p ON p.id=b.page_id
        WHERE t.status='ai_draft' AND b.active=1 AND p.deleted_at IS NULL AND t.language='zh_CN'
        ORDER BY p.display_order,b.reading_order,b.sequence""").fetchall()
    if not rows: return
    current = next((i for i,r in enumerate(rows) if r["block_id"] == workspace.selected_block), -1)
    row = rows[(current+1)%len(rows)]
    index = next(i for i,p in enumerate(workspace.model.pages) if p["id"] == row["page_id"])
    workspace.panel.setCurrentIndex(workspace.model.index(index))
    QTimer.singleShot(0, lambda: workspace.select_block(row["block_id"]))
