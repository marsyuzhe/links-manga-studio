"""Startup and workspace host; secondary workspaces are created on explicit navigation."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QMenu, QPushButton, QToolButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from app.diagnostics import collect
from app.i18n import LanguageManager
from app.project import ProjectError, ProjectService
from app.resources import resource_path
from app.themes import ThemeManager
from app.ui.icons import icon
from app.ui.components import ActionButton, SectionHeader, exec_dialog, localize_buttons
from app.ui.settings_dialog import SettingsDialog
from app.ui.about_dialog import AboutDialog
from app.branding import DISPLAY_NAME, AUTHOR_EN, TAGLINE_EN, TAGLINE_ZH
from app.ui.workspace import Workspace
from app.ui.workspace_chrome import CommandButton


class NewProjectDialog(QDialog):
    def __init__(self, language: LanguageManager, parent=None) -> None:
        super().__init__(parent)
        self.language = language
        tr = language.tr
        self.setWindowTitle(tr("dialog.new_project"))
        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.parent_path = QLineEdit(str(Path.home() / "Documents"))
        browse = QPushButton(tr("action.browse"))
        browse.clicked.connect(self._browse)
        folder = QWidget()
        row = QHBoxLayout(folder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.parent_path)
        row.addWidget(browse)
        self.name = QLineEdit()
        self.mode = QComboBox()
        self.mode.addItem(tr("dialog.copy"), "copy")
        self.mode.addItem(tr("dialog.reference"), "reference")
        layout.addRow(tr("dialog.parent_folder"), folder)
        layout.addRow(tr("dialog.project_name"), self.name)
        layout.addRow(tr("dialog.source_mode"), self.mode)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.confirm"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.cancel"))
        localize_buttons(buttons, tr)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, self.language.tr("dialog.choose_parent"), self.parent_path.text())
        if selected:
            self.parent_path.setText(selected)


class MainWindow(QMainWindow):
    def __init__(self, service: ProjectService, log_path: Path) -> None:
        super().__init__()
        self.service = service
        self.language = LanguageManager(service.config)
        self.theme = ThemeManager(service.config)
        self.theme.apply()
        self.log_path = log_path
        self.setWindowIcon(QIcon(str(resource_path("assets/icons/app_icon.ico"))))
        self.setWindowTitle(DISPLAY_NAME)
        self.resize(1366, 768)
        self.setAcceptDrops(True)
        self.stack = QStackedWidget()
        self._translation_center = None
        self._glossary_workspace = None
        self.setCentralWidget(self.stack)
        self._create_startup()
        self._create_workspace()
        self._create_menu()
        self._workspace_language=self.language.language
        self._first_hint()
        self.language.changed.connect(self.retranslate)
        self.retranslate()
        self.update_theme()

    @property
    def translation_center(self):
        """Own one translation view, constructed only on explicit first access."""
        if self._translation_center is None:
            from .translation_center import TranslationCenter
            self._translation_center = TranslationCenter(self)
            self.stack.addWidget(self._translation_center)
        return self._translation_center

    @property
    def glossary_workspace(self):
        """Keep project rows out of startup; existing view access remains compatible."""
        if self._glossary_workspace is None:
            from .glossary_workspace import GlossaryWorkspace
            self._glossary_workspace = GlossaryWorkspace(self)
            self.stack.addWidget(self._glossary_workspace)
        return self._glossary_workspace

    def show_manga(self):
        if self._glossary_workspace is not None:
            self._glossary_workspace.save_character()
        self.stack.setCurrentWidget(self.workspace if self.service.path else self.stack.widget(0))
        self.toolbar.setVisible(self.service.path is not None)

    def show_translation_center(self,scope=None):
        if not self.service.connection:return
        self.workspace._save_translation_debounced()
        if self._glossary_workspace is not None:
            self._glossary_workspace.save_character()
        self.stack.setCurrentWidget(self.translation_center)
        self.translation_center.tabs.setCurrentIndex(0)
        self.translation_center.load(scope)

    def show_glossary(self):
        if not self.service.connection:return
        if self.workspace.jobs:
            self.statusBar().showMessage("任务运行时术语库只读，请先暂停任务。" if self.language.language=="zh_CN" else "Pause the task before editing glossary.",5000)
            return
        self.glossary_workspace.load()
        self.stack.setCurrentWidget(self.glossary_workspace)

    def reset_panel_layout(self):
        self.left_action.setChecked(True);self.right_action.setChecked(True)
        self.workspace.left_tabs.show();self.workspace.inspector_panel.show();self.workspace.tool_rail.show()
        self.workspace.main_splitter.setSizes([280,760,320])

    def _create_startup(self) -> None:
        page = QWidget()
        page.setProperty("role", "startup")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(740)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        outer.addWidget(content, 3)
        outer.addStretch(1)
        title = QLabel(DISPLAY_NAME)
        title.setProperty("role", "title")
        layout.addWidget(title)
        self.subtitle = QLabel()
        self.subtitle.setProperty("role", "muted")
        layout.addWidget(self.subtitle)
        dropzone = QWidget()
        self.dropzone = dropzone
        dropzone.setProperty("role", "dropzone")
        drop_layout = QVBoxLayout(dropzone)
        drop_layout.setContentsMargins(16, 16, 16, 16)
        drop_layout.setSpacing(8)
        self.drop_icon = QLabel()
        self.drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.drop_icon)
        self.drop_hint = QLabel()
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setProperty("role", "drop_title")
        drop_layout.addWidget(self.drop_hint)
        self.start_logo = QLabel()
        self.start_logo.setPixmap(QPixmap(str(resource_path("assets/icons/app_icon_128.png"))).scaled(32,32,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        # Small product mark, no hero artwork.
        layout.insertWidget(1,self.start_logo)
        self.drop_formats = QLabel("PDF · JPG · PNG · WEBP · BMP")
        self.drop_formats.setProperty("role", "muted")
        self.drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.drop_formats)
        drop_layout.addSpacing(8)
        drop_actions = QHBoxLayout()
        drop_actions.setSpacing(8)
        self.open_pdf_button = ActionButton(variant="primary", icon=icon("pdf", "#10141D"))
        self.open_pdf_button.clicked.connect(self.open_comic_as_project)
        self.new_button = ActionButton(icon=icon("add"))
        self.new_button.clicked.connect(self.new_project)
        self.open_button = ActionButton(icon=icon("folder"))
        self.open_button.clicked.connect(self.open_project_dialog)
        self.new_button.hide()
        for button in (self.open_pdf_button, self.open_button):
            drop_actions.addWidget(button)
        drop_layout.addLayout(drop_actions)
        layout.addWidget(dropzone)
        self.recent_label = SectionHeader()
        layout.addWidget(self.recent_label)
        self.recent = QListWidget()
        self.recent.setMaximumHeight(240)
        self.recent.itemDoubleClicked.connect(lambda item: self.open_project(Path(item.data(Qt.ItemDataRole.UserRole))))
        self.recent.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent.customContextMenuRequested.connect(self._recent_context_menu)
        layout.addWidget(self.recent)
        self.recent_empty = QLabel()
        self.recent_empty.setProperty("role", "muted")
        layout.addWidget(self.recent_empty)
        self.author_footer = QLabel()
        self.author_footer.setProperty("role", "muted")
        layout.addWidget(self.author_footer)
        layout.addStretch(1)
        self.stack.addWidget(page)
        self.refresh_recent()

    def _create_workspace(self) -> None:
        self.workspace = Workspace(self.service.config, self.language, self)
        self.workspace.status_changed.connect(self._on_workspace_status)
        self.workspace.busy_changed.connect(self._busy_changed)
        self.quality_badge = ActionButton(variant="ghost")
        self.quality_badge.clicked.connect(self._open_quality_panel)
        self.quality_badge.hide()
        self.statusBar().addPermanentWidget(self.quality_badge)
        self.task_indicator = QToolButton()
        self.task_indicator.setProperty("variant", "ghost")
        self.task_indicator.clicked.connect(self._open_task_panel)
        self.task_indicator.hide()
        self.statusBar().addPermanentWidget(self.task_indicator)
        self.workspace.task_progress.connect(self._task_progress)
        self.stack.addWidget(self.workspace)

    def _on_workspace_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        count = self.workspace.quality_warning_count
        self.quality_badge.setText(self.language.tr("ui.quality_count", count=count))
        self.quality_badge.setVisible(count > 0 and self.stack.currentWidget() is self.workspace)

    def _open_quality_panel(self) -> None:
        if self.workspace.quality_list.count():
            self.workspace.bottom_tabs.setCurrentIndex(3)
            self.workspace.bottom_tabs.show()
        else:
            self.workspace.show_quality_check()

    def _create_menu(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.project_actions = []
        for handler in (self.new_project, self.open_project_dialog, self.close_project, self.close):
            action = QAction(self)
            action.triggered.connect(handler)
            self.file_menu.addAction(action)
            self.project_actions.append(action)
        self.recent_menu = self.file_menu.addMenu("")
        self.save_action = QAction(self)
        self.save_action.triggered.connect(self.save_project)
        self.save_action.setEnabled(self.service.path is not None)
        self.file_menu.addAction(self.save_action)
        self.backup_action = QAction(self)
        self.backup_action.triggered.connect(self.backup_project)
        self.backup_action.setEnabled(self.service.path is not None)
        self.file_menu.addAction(self.backup_action)
        for key in ("images", "folder", "pdf"):
            self.file_menu.addAction(self.workspace.actions[key])
        self.edit_menu = self.menuBar().addMenu("")
        self.view_menu = self.menuBar().addMenu("")
        self.edit_menu.addAction(self.workspace.actions["undo"])
        self.edit_menu.addAction(self.workspace.actions["redo"])
        self.edit_menu.addSeparator()
        for key in ("copy_style", "paste_style", "duplicate_block", "delete_block"):
            self.edit_menu.addAction(self.workspace.actions[key])
        for key in ("erase_quick", "erase_refill", "fill_translation"):
            self.edit_menu.addAction(self.workspace.actions[key])
        for key in ("fit", "actual", "zoom_in", "zoom_out", "goto"):
            self.view_menu.addAction(self.workspace.actions[key])
        self.page_info_action = QAction(self)
        self.page_info_action.setCheckable(True)
        self.page_info_action.toggled.connect(self._toggle_page_info)
        self.view_menu.addAction(self.page_info_action)
        self.bottom_action = QAction(self)
        self.bottom_action.setCheckable(True)
        self.bottom_action.toggled.connect(self._toggle_bottom)
        self.view_menu.addAction(self.bottom_action)
        self.left_action = QAction(self)
        self.left_action.setCheckable(True)
        self.left_action.setChecked(True)
        self.left_action.toggled.connect(self.workspace.left_tabs.setVisible)
        self.view_menu.addAction(self.left_action)
        self.right_action = QAction(self)
        self.right_action.setCheckable(True)
        self.right_action.setChecked(True)
        self.right_action.toggled.connect(self.workspace.inspector_panel.setVisible)
        self.view_menu.addAction(self.right_action)
        self.page_info_action.setChecked(bool(self.service.config.data.get("show_page_info", False)))
        self.bottom_action.setChecked(bool(self.service.config.data.get("show_bottom", False)))
        self.focus_action = QAction(self)
        self.focus_action.setShortcut("Ctrl+Tab")
        self.focus_action.triggered.connect(self.toggle_focus)
        self.view_menu.addAction(self.focus_action)
        self.reset_layout_action = QAction("重置面板布局" if self.language.language=="zh_CN" else "Reset panel layout",self)
        self.reset_layout_action.triggered.connect(self.reset_panel_layout)
        self.view_menu.addAction(self.reset_layout_action)
        self.advanced_action = QAction(self)
        self.advanced_action.setCheckable(True)
        self.advanced_action.toggled.connect(lambda enabled: self.simple_action.setChecked(not enabled))
        self.view_menu.addAction(self.advanced_action)
        self.project_menu = self.menuBar().addMenu("")
        self.project_menu.addAction(self.workspace.actions["relocate"])
        self.project_menu.addAction(self.workspace.actions["batches"])
        self.project_menu.addAction(self.workspace.actions["project_styles"])
        self.project_menu.addAction(self.workspace.actions["replace_fonts"])
        self.project_menu.addAction(self.workspace.actions["quality_check"])
        self.project_menu.addAction(self.workspace.actions["up"])
        self.project_menu.addAction(self.workspace.actions["down"])
        self.ocr_menu = self.menuBar().addMenu("")
        for key in ("ocr_page", "ocr_all", "ocr_resume", "models"):
            self.ocr_menu.addAction(self.workspace.actions[key])
        self.project_translation_menu = self.project_menu.addMenu("")
        self.project_translation_menu.addAction(self.workspace.actions["ai_project"])
        self.translation_menu = self.menuBar().addMenu("")
        self.translation_scope_actions = {}
        for scope, cn, en in (("block","翻译当前文本","Translate current text"),("page","翻译当前页","Translate current page"),("selected","翻译所选页面","Translate selected pages"),("batch","翻译当前批次","Translate current batch"),("project","翻译整个项目","Translate entire project")):
            action = QAction(cn if self.language.language == "zh_CN" else en,self)
            action.triggered.connect(lambda checked=False,scope=scope:self.show_translation_center(scope))
            self.translation_menu.addAction(action)
            self.translation_scope_actions[scope]=action
        self.translation_menu.addSeparator()
        self.center_action = QAction("翻译中心" if self.language.language=="zh_CN" else "Translation Center",self)
        self.center_action.triggered.connect(lambda:self.show_translation_center())
        self.translation_menu.addAction(self.center_action)
        for key in ("ai_project", "ai_next", "word_export", "word_import"):
            self.translation_menu.addAction(self.workspace.actions[key])
        self.export_menu = self.menuBar().addMenu("")
        for key in ("export_source", "export_page", "export_batch", "export_all", "export_resume"):
            self.export_menu.addAction(self.workspace.actions[key])
        self.settings_menu = self.menuBar().addMenu("")
        self.preferences_action = QAction(self)
        self.preferences_action.triggered.connect(self.show_settings)
        self.settings_menu.addAction(self.preferences_action)
        self.settings_menu.addSeparator()
        self.language_menu = self.settings_menu.addMenu("")
        self.language_actions = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, name in (("zh_CN", "简体中文"), ("en_US", "English")):
            action = QAction(name, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, language=code: self.language.set_language(language))
            group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[code] = action
        self._build_workflow_toolbar()
        self.simple_action = QAction(self)
        self.simple_action.setCheckable(True)
        self.simple_action.setChecked(bool(self.service.config.data.get("simple_mode", True)))
        self.simple_action.toggled.connect(self.set_simple_mode)
        self.settings_menu.addAction(self.simple_action)
        self.set_simple_mode(self.simple_action.isChecked())
        self.advanced_action.setChecked(not self.simple_action.isChecked())
        self.help_menu = self.menuBar().addMenu("")
        self.about_action = QAction(self)
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.about_action)
        self.help_menu.addSeparator()
        self.diagnostic_action = QAction(self)
        self.diagnostic_action.triggered.connect(self.show_diagnostics)
        self.help_menu.addAction(self.diagnostic_action)
        self.open_log_action = QAction(self)
        self.open_log_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path.parent))))
        self.help_menu.addAction(self.open_log_action)
        self.refresh_recent()

    def _build_workflow_toolbar(self) -> None:
        self.toolbar = self.addToolBar("")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setProperty("role", "commandbar")
        self.toolbar.setFixedHeight(42)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.workflow_buttons = {}
        for key, glyph, actions, handler in (
            ("import", "folder", ("images", "folder", "pdf"), self.workspace.import_images),
            ("ocr", "ocr", ("ocr_page", "ocr_all", "ocr_resume"), self.workspace.ocr_current_page),
            ("translation", "text", ("ai_page", "ai_next", "word_export", "word_import", "ai_project"), lambda:self.show_translation_center("page")),
            ("export", "export", ("export_page", "export_batch", "export_all", "export_source", "export_resume"), self.workspace.export_all_pages),
        ):
            button = CommandButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            menu = QMenu(button)
            if key == "translation":
                for scope in ("block","page","selected","batch","project"): menu.addAction(self.translation_scope_actions[scope])
                menu.addSeparator();menu.addAction(self.center_action)
            else:
                for action_key in actions: menu.addAction(self.workspace.actions[action_key])
            button.setMenu(menu)
            button.clicked.connect(handler)
            self.toolbar.addWidget(button)
            self.workflow_buttons[key] = (button, glyph)
        spacer = QWidget()
        spacer.setProperty("role", "chromeSpacer")
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.page_counter = QLabel("— / —")
        self.page_counter.setMinimumWidth(68)
        self.page_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for key, glyph in (("previous", "previous"), ("next", "next")):
            action = self.workspace.actions[key]
            action.setIcon(icon(glyph, size=18))
            self.toolbar.addAction(action)
            if key == "previous": self.toolbar.addWidget(self.page_counter)
            nav_button = self.toolbar.widgetForAction(action)
            nav_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            nav_button.setProperty("role", "icon")
            nav_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            nav_button.setFixedSize(32,32)
        self.zoom_choice = QComboBox()
        self.zoom_choice.setFixedWidth(90)
        self.zoom_choice.setEditable(True)
        self.toolbar.addWidget(self.zoom_choice)
        self.zoom_choice.addItems(["Fit", "50%", "100%", "200%", "400%"])
        self.zoom_choice.activated.connect(self._apply_zoom_choice)
        self.zoom_choice.lineEdit().returnPressed.connect(self._apply_zoom_text)
        self.workspace.canvas.zoom_changed.connect(self._update_toolbar_position)
        self.workspace.panel.selectionModel().currentChanged.connect(self._update_toolbar_position)
        self.toolbar.hide()

    def retranslate(self, *_args) -> None:
        tr = self.language.tr
        self.subtitle.setText(TAGLINE_ZH if self.language.language == "zh_CN" else TAGLINE_EN)
        self.author_footer.setText(f"Created by {AUTHOR_EN}")
        self.drop_hint.setText("将漫画拖到这里" if self.language.language == "zh_CN" else "Drop manga here")
        self.new_button.setText(tr("action.new_project"))
        self.open_button.setText(tr("action.open_project"))
        self.open_pdf_button.setText(tr("ui.open_comic"))
        for key, (button, glyph) in self.workflow_buttons.items():
            button.setText(tr("ui.workflow_"+key))
            button.setToolTip(tr("ui.workflow_"+key))
        self.open_pdf_button.setToolTip("打开 PDF，并自动创建一个漫画项目。" if self.language.language == "zh_CN"
                                        else "Open a PDF and create a manga project automatically.")
        self.recent_label.setText(tr("panel.recent"))
        self.recent_empty.setText("最近打开的项目会显示在这里。" if self.language.language == "zh_CN" else
                                  "Recently opened projects appear here.")
        for menu, key in ((self.file_menu, "menu.file"), (self.view_menu, "menu.view"),
                          (self.edit_menu, "menu.edit"),
                          (self.project_menu, "menu.project"), (self.ocr_menu, "menu.ocr"),
                          (self.translation_menu, "menu.translation"), (self.export_menu, "menu.export"),
                          (self.settings_menu, "menu.settings"), (self.language_menu, "menu.language"),
                          (self.help_menu, "menu.help")):
            menu.setTitle(tr(key))
        for action, key in zip(self.project_actions, ("action.new_project", "action.open_project", "action.close_project", "action.exit")):
            action.setText(tr(key))
        self.backup_action.setText(tr("action.backup_project"))
        self.toolbar.setWindowTitle(tr("panel.pages"))
        self.toolbar.setAccessibleName(tr("panel.pages"))
        self._update_toolbar_position()
        self.page_info_action.setText(tr("view.page_info"))
        self.bottom_action.setText(tr("view.bottom"))
        self.left_action.setText(tr("view.left"))
        self.right_action.setText(tr("view.right"))
        self.focus_action.setText(tr("view.focus"))
        self.advanced_action.setText("高级模式" if self.language.language == "zh_CN" else "Advanced Mode")
        self.simple_action.setText(tr("settings.simple"))
        self.preferences_action.setText("首选项…" if self.language.language == "zh_CN" else "Preferences…")
        self.project_translation_menu.setTitle(tr("panel.translation"))
        self.recent_menu.setTitle(tr("panel.recent"))
        self.save_action.setText(tr("action.save_project"))
        self.diagnostic_action.setText(tr("action.diagnostics"))
        self.about_action.setText("关于" if self.language.language == "zh_CN" else "About")
        self.open_log_action.setText(tr("action.open_logs"))
        self.language_actions[self.language.language].setChecked(True)
        self.workspace.retranslate()
        if self._workspace_language != self.language.language and not self.workspace.jobs and not (
                self._translation_center and self._translation_center.check_job):
            current=self.stack.currentWidget();old_center=self._translation_center;old_glossary=self._glossary_workspace
            task_id=old_center.task_id if old_center else None;tab=old_center.tabs.currentIndex() if old_center else 0
            # Rebuild only views that existed; changing locale must not defeat lazy startup.
            if old_glossary:old_glossary.save_character()
            if old_center:old_center.timer.stop()
            self._translation_center=None;self._glossary_workspace=None
            if old_center and current is old_center:
                self.translation_center.task_id=task_id;self.stack.setCurrentWidget(self.translation_center)
                self.translation_center.load();self.translation_center.tabs.setCurrentIndex(tab)
            elif old_glossary and current is old_glossary:
                self.stack.setCurrentWidget(self.glossary_workspace);self.glossary_workspace.load()
            for old in (old_center,old_glossary):
                if old:self.stack.removeWidget(old);old.deleteLater()
            self._workspace_language=self.language.language
        if hasattr(self,"translation_scope_actions"):
            for scope,cn,en in (("block","翻译当前文本","Translate current text"),("page","翻译当前页","Translate current page"),("selected","翻译所选页面","Translate selected pages"),("batch","翻译当前批次","Translate current batch"),("project","翻译整个项目","Translate entire project")):
                self.translation_scope_actions[scope].setText(cn if self.language.language=="zh_CN" else en)
            self.center_action.setText("翻译中心" if self.language.language=="zh_CN" else "Translation Center")
            self.reset_layout_action.setText("重置面板布局" if self.language.language=="zh_CN" else "Reset panel layout")
        if self.service.path is None:
            self.statusBar().showMessage(tr("status.ready"))
        else:
            self.workspace.update_status()

    def refresh_recent(self) -> None:
        self.recent.clear()
        metadata = self.service.config.data.get("recent_project_meta", {})
        for path in self.service.config.recent_projects:
            project = Path(path)
            detail = metadata.get(path, {})
            pages = detail.get("pages")
            source_type = detail.get("source_type", "")
            count = f"  ·  {source_type + ' · ' if source_type else ''}{pages} {'页' if self.language.language == 'zh_CN' else 'pages'}" if pages is not None else ""
            opened = f"  ·  {detail['opened']}" if detail.get("opened") else ""
            item = QListWidgetItem(f"{project.stem}{count}{opened}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(project.stem)
            item.setSizeHint(QSize(0, 40))
            thumb = next((project / "cache" / "thumbnails").glob("*.png"), None) if project.exists() else None
            if thumb:
                preview_icon = QIcon(QPixmap(str(thumb)).scaled(28, 34, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                preview_icon = icon("folder", size=20)
            self.recent.addItem(item)
            row = QWidget(self.recent)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 2, 4, 2)
            row_layout.setSpacing(6)
            preview = QLabel()
            preview.setFixedSize(26, 32)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setPixmap(preview_icon.pixmap(24, 30))
            row_layout.addWidget(preview)
            open_button = QPushButton(item.text())
            open_button.setToolTip("")
            open_button.setProperty("role", "recentOpen")
            open_button.clicked.connect(lambda checked=False, target=path: self.open_project(Path(target)))
            row_layout.addWidget(open_button, 1)
            menu_button = QPushButton("⋯")
            menu_button.setFixedWidth(30)
            menu_button.setToolTip("更多操作" if self.language.language == "zh_CN" else "More actions")
            menu_button.clicked.connect(lambda checked=False, target=path, button=menu_button:
                self._recent_actions_menu(target, button.mapToGlobal(button.rect().bottomLeft())))
            row_layout.addWidget(menu_button)
            self.recent.setItemWidget(item, row)
        self.recent.setFixedHeight(min(240, max(48, self.recent.count() * 42 + 8)))
        self.recent.setVisible(self.recent.count() > 0)
        self.recent_empty.setVisible(self.recent.count() == 0)
        if hasattr(self, "recent_menu"):
            self.recent_menu.clear()
            for path in self.service.config.recent_projects:
                action = self.recent_menu.addAction(Path(path).name)
                action.setToolTip(Path(path).stem)
                action.triggered.connect(lambda checked=False, target=path: self.open_project(Path(target)))

    def _recent_context_menu(self, position) -> None:
        item = self.recent.itemAt(position)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        self._recent_actions_menu(path, self.recent.viewport().mapToGlobal(position))

    def _recent_actions_menu(self, path: str, position) -> None:
        menu = QMenu(self)
        menu.addAction("打开" if self.language.language == "zh_CN" else "Open",
                       lambda: self.open_project(Path(path)))
        menu.addAction("打开所在文件夹" if self.language.language == "zh_CN" else "Open containing folder",
                       lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent))))
        menu.addAction("从最近项目移除" if self.language.language == "zh_CN" else "Remove from recent",
                       lambda: self._remove_recent(path))
        menu.exec(position)

    def _remove_recent(self, path: str) -> None:
        self.service.config.data["recent_projects"] = [p for p in self.service.config.recent_projects if p != path]
        self.service.config.data.get("recent_project_meta", {}).pop(path, None)
        self.service.config.save()
        self.refresh_recent()

    def save_project(self) -> None:
        if self.service.connection:
            self.service.connection.commit()
            self.service.config.save()
            self.statusBar().showMessage(self.language.tr("status.project_saved"), 5000)

    def show_settings(self) -> None:
        exec_dialog(SettingsDialog(self))

    def show_about(self) -> None:
        exec_dialog(AboutDialog(self))

    def set_theme(self, mode: str) -> None:
        self.theme.set_mode(mode)
        self.update_theme()

    def update_theme(self) -> None:
        tokens = self.theme.tokens
        for button, glyph in self.workflow_buttons.values(): button.setIcon(icon(glyph, tokens["text_secondary"], 16))
        self.workspace.update_theme(tokens)
        self.drop_icon.setPixmap(icon("image", tokens["text_muted"], 30).pixmap(30, 30))
        for button, glyph in ((self.open_pdf_button, "pdf"), (self.new_button, "add"),
                              (self.open_button, "folder")):
            button.setIcon(icon(glyph, tokens["accent_text"] if button is self.open_pdf_button
                                else tokens["text_secondary"]))
        for key, glyph in (("pdf", "pdf"), ("images", "image"), ("folder", "folder"),
                           ("ocr_page", "ocr"), ("export_source", "text"),
                           ("erase_refill", "erase"), ("export_all", "export"),
                           ("previous", "previous"), ("next", "next")):
            self.workspace.actions[key].setIcon(icon(glyph,
                tokens["accent_text"] if key == "erase_refill" else tokens["text_secondary"], 16))
        self.refresh_recent()
        self.update()

    def new_project(self) -> None:
        dialog = NewProjectDialog(self.language, self)
        if exec_dialog(dialog) == QDialog.DialogCode.Accepted:
            try:
                self.service.create_project(Path(dialog.parent_path.text()), dialog.name.text(), dialog.mode.currentData())
                self._project_opened()
            except (ProjectError, OSError) as exc:
                logging.exception("Project creation failed")
                QMessageBox.critical(self, self.language.tr("dialog.project_error"), self.language.user_error(str(exc)))

    def open_project_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.language.tr("dialog.open_project"))
        if folder:
            self.open_project(Path(folder))

    def open_comic_as_project(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, self.language.tr("ui.open_comic"), "",
            "Comics (*.pdf *.PDF *.jpg *.jpeg *.png *.webp *.bmp)")
        if names: self.import_dropped_paths([Path(name) for name in names])

    def _open_task_panel(self):
        self.workspace.bottom_tabs.setCurrentIndex(0)
        self.workspace.bottom_tabs.show()

    def _task_progress(self, value, total, text):
        self.task_indicator.setVisible(bool(self.workspace.jobs))
        task = self.language.progress_text(text)
        self.task_indicator.setText(f"{task} {round(100*value/max(1,total))}%")

    def open_pdf_as_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.language.tr("action.open_pdf_project"), "", "PDF (*.pdf *.PDF)")
        if filename:
            self.import_dropped_paths([Path(filename)])

    def import_dropped_paths(self, paths: list[Path]) -> None:
        supported = [path for path in paths if path.is_dir() or path.suffix.lower() in
                     (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp")]
        if not supported:
            return
        preview = "\n".join(str(path) for path in supported[:8])
        if len(supported) > 8:
            preview += f"\n… +{len(supported)-8}"
        message = self.language.tr("dialog.drop_preview", count=len(supported), files=preview)
        if QMessageBox.question(self, self.language.tr("dialog.drop_title"), message,
                                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Ok:
            return
        if self.service.path is not None:
            choice = QMessageBox.question(self, self.language.tr("dialog.drop_title"),
                self.language.tr("dialog.drop_existing"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.No:
                if self.workspace.jobs:
                    QMessageBox.information(self, self.language.tr("dialog.operation_running"), self.language.tr("dialog.wait_operation"))
                    return
                self.close_project()
        if self.service.path is None:
            first = supported[0]
            base = first.stem if first.is_file() else first.name
            parent = first.parent
            name = base
            number = 2
            while (parent / f"{name}.lmw").exists():
                name = f"{base}-{number}"
                number += 1
            try:
                self.service.create_project(parent, name, "copy")
                self._project_opened()
            except (ProjectError, OSError) as exc:
                logging.exception("Drop project creation failed")
                QMessageBox.critical(self, self.language.tr("dialog.project_error"), self.language.user_error(str(exc)))
                return
        self.workspace.import_paths(supported)

    def set_simple_mode(self, enabled: bool) -> None:
        self.service.config.data["simple_mode"] = bool(enabled)
        self.service.config.save()
        self.advanced_action.blockSignals(True)
        self.advanced_action.setChecked(not enabled)
        self.advanced_action.blockSignals(False)
        self.workspace.set_simple_mode(enabled)

    def _toggle_page_info(self, enabled: bool) -> None:
        self.workspace.inspector.setVisible(enabled)
        self.service.config.data["show_page_info"] = bool(enabled)
        self.service.config.save()

    def _toggle_bottom(self, enabled: bool) -> None:
        self.workspace.bottom_tabs.setVisible(enabled)
        self.service.config.data["show_bottom"] = bool(enabled)
        self.service.config.save()

    def toggle_focus(self) -> None:
        if self.stack.currentWidget() is not self.workspace:
            return
        focused = self.workspace.left_tabs.isVisible()
        self.workspace.left_tabs.setVisible(not focused)
        self.workspace.tool_rail.setVisible(not focused)
        self.workspace.right_tabs.parentWidget().setVisible(not focused)
        self.workspace.bottom_tabs.setVisible(False if focused else self.bottom_action.isChecked())

    def _apply_zoom_choice(self, index: int) -> None:
        value = self.zoom_choice.itemText(index)
        if value == "Fit":
            self.workspace.canvas.fit()
        else:
            self.workspace.canvas.set_zoom(float(value.rstrip("%")) / 100)

    def _apply_zoom_text(self) -> None:
        value = self.zoom_choice.currentText().strip().rstrip("%")
        try:
            self.workspace.canvas.set_zoom(float(value) / 100)
        except ValueError:
            self._update_toolbar_position()

    def _update_toolbar_position(self, *_args) -> None:
        workspace = self.workspace
        total = len(workspace.model.pages)
        self.page_counter.setText(f"{workspace.current_row + 1 if workspace.current_row >= 0 else '—'} / {total or '—'}")
        if hasattr(self, "zoom_choice"):
            zoom = workspace.canvas.transform().m11() * 100
            self.zoom_choice.setEditText("Fit" if workspace.canvas.fit_mode else f"{zoom:.0f}%")

    def _first_hint(self) -> None:
        if not self.service.config.data.get("first_hint_seen"):
            self.statusBar().showMessage(self.language.tr("status.first_hint"), 15000)
            self.service.config.data["first_hint_seen"] = True
            self.service.config.save()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            self._set_drop_highlight(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_highlight(False)
        super().dragLeaveEvent(event)

    def _set_drop_highlight(self, enabled: bool) -> None:
        self.dropzone.setProperty("dragActive", enabled)
        self.dropzone.style().unpolish(self.dropzone)
        self.dropzone.style().polish(self.dropzone)

    def dropEvent(self, event) -> None:
        self._set_drop_highlight(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.import_dropped_paths(paths)
        event.acceptProposedAction()

    def open_project(self, path: Path) -> None:
        if self._glossary_workspace is not None:
            self._glossary_workspace.save_character()
        try:
            self.service.open_project(path)
            self._project_opened()
        except ProjectError as exc:
            QMessageBox.critical(self, self.language.tr("dialog.project_error"), self.language.user_error(str(exc)))

    def _project_opened(self) -> None:
        if self._glossary_workspace is not None:
            self._glossary_workspace.service=None
            self._glossary_workspace.character_id=None
        if self._translation_center is not None:
            self._translation_center.task_id=None
        self.workspace.load_project(self.service.path, self.service.connection)
        self.stack.setCurrentIndex(1)
        self.toolbar.show()
        self.setWindowTitle(f"{self.service.path.stem} — {DISPLAY_NAME}")
        self._update_toolbar_position()
        self.workspace.update_status()
        recent_meta = self.service.config.data.setdefault("recent_project_meta", {})
        recent_meta[str(self.service.path)] = {"pages": len(self.workspace.model.pages),
                                               "source_type": "PDF" if any(p.get("source_kind") == "pdf"
                                                                           for p in self.workspace.model.pages) else "Images",
                                               "opened": datetime.now().strftime("%m/%d %H:%M")}
        self.service.config.save()
        self.refresh_recent()
        self.backup_action.setEnabled(True)
        self.save_action.setEnabled(True)

    def close_project(self) -> None:
        if self.workspace.jobs:
            return
        if self.service.path:
            recent_meta = self.service.config.data.setdefault("recent_project_meta", {})
            recent_meta.setdefault(str(self.service.path), {})["pages"] = len(self.workspace.model.pages)
            recent_meta[str(self.service.path)]["source_type"] = (
                "PDF" if any(p.get("source_kind") == "pdf" for p in self.workspace.model.pages) else "Images")
            self.service.config.save()
        if self._glossary_workspace is not None:
            self._glossary_workspace.save_character()
        if self._translation_center is not None:
            self._translation_center.timer.stop()
            self._translation_center.task_id = None
        self.workspace.unload()
        self.service.close_project()
        if self._glossary_workspace is not None:
            self._glossary_workspace.service=None
            self._glossary_workspace.character_id=None
        self.stack.setCurrentIndex(0)
        self.toolbar.hide()
        self.quality_badge.hide()
        self.refresh_recent()
        self.setWindowTitle(DISPLAY_NAME)
        self.task_indicator.hide()
        self.statusBar().showMessage(self.language.tr("status.ready"))
        self._update_toolbar_position()
        self.backup_action.setEnabled(False)
        self.save_action.setEnabled(False)

    def backup_project(self) -> None:
        try:
            path = self.service.backup_project()
            QMessageBox.information(self, self.language.tr("action.backup_project"),
                                    self.language.tr("dialog.backup_created", path=str(path)))
        except Exception as exc:
            logging.exception("Backup failed")
            QMessageBox.critical(self, self.language.tr("dialog.project_error"), str(exc))

    def show_diagnostics(self) -> None:
        info = collect(self.service.path, self.log_path)
        info[self.language.tr("dialog.cache_limit")] = f"{self.service.config.image_cache_mb} MB"
        info[self.language.tr("dialog.cache_used")] = f"{self.workspace.cache.used_bytes / 1024**2:.1f} MB"
        QMessageBox.information(self, self.language.tr("dialog.diagnostics"),
                                "\n".join(f"{key}: {value}" for key, value in info.items()))

    def closeEvent(self, event) -> None:
        if self._translation_center and self._translation_center.check_job and self._translation_center.check_job.isRunning():
            from PySide6.QtCore import QTimer
            self._translation_center.check_job.finished.connect(lambda:QTimer.singleShot(0,self.close))
            event.ignore();return
        if getattr(self.workspace,"ai_job",None) and self.workspace.ai_job.isRunning():
            from app.tasks.service import TaskService
            from PySide6.QtCore import QTimer
            TaskService(self.service.connection).set_status(self.workspace.ai_task_id,"paused")
            self.workspace.ai_job.finished.connect(lambda:QTimer.singleShot(0,self.close))
            self.statusBar().showMessage("当前请求完成后保存并退出。" if self.language.language=="zh_CN" else "Saving and closing after current requests finish.")
            event.ignore();return
        if self.workspace.jobs:
            QMessageBox.information(self, self.language.tr("dialog.operation_running"), self.language.tr("dialog.wait_operation"))
            event.ignore()
            return
        if self._glossary_workspace is not None:
            self._glossary_workspace.save_character()
        if self._translation_center is not None:
            self._translation_center.timer.stop()
            self._translation_center.task_id = None
        self.workspace.unload()
        self.service.close_project()
        super().closeEvent(event)

    def _busy_changed(self, busy: bool) -> None:
        if not busy and self._workspace_language!=self.language.language:
            self.retranslate()
        self.task_indicator.setVisible(busy)
        if busy: self.task_indicator.setText(self.language.tr(self.workspace._job_title))
        for button, glyph in self.workflow_buttons.values(): button.setEnabled(not busy)
        for action in getattr(self, "project_actions", []):
            action.setEnabled(not busy)
        self.backup_action.setEnabled(not busy and self.service.path is not None)
