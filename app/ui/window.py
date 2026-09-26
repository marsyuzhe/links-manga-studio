"""Startup screen and empty project workspace."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QMenu, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from app.diagnostics import collect
from app.i18n import LanguageManager
from app.project import ProjectError, ProjectService
from app.resources import resource_path
from app.themes import ThemeManager
from app.ui.icons import icon
from app.ui.components import ActionButton, SectionHeader
from app.ui.settings_dialog import SettingsDialog
from app.ui.about_dialog import AboutDialog
from app.branding import DISPLAY_NAME, AUTHOR_EN, TAGLINE_EN, TAGLINE_ZH
from app.ui.workspace import Workspace


class NewProjectDialog(QDialog):
    def __init__(self, language: LanguageManager, parent=None) -> None:
        super().__init__(parent)
        self.language = language
        tr = language.tr
        self.setWindowTitle(tr("dialog.new_project"))
        layout = QFormLayout(self)
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
        self.resize(1100, 720)
        self.setAcceptDrops(True)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._create_startup()
        self._create_workspace()
        self._create_menu()
        self._first_hint()
        self.language.changed.connect(self.retranslate)
        self.retranslate()
        self.update_theme()

    def _create_startup(self) -> None:
        page = QWidget()
        page.setProperty("role", "startup")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(740)
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
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
        drop_layout.setContentsMargins(24, 20, 24, 20)
        drop_layout.setSpacing(8)
        self.drop_icon = QLabel()
        self.drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.drop_icon)
        self.drop_hint = QLabel()
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setProperty("role", "drop_title")
        drop_layout.addWidget(self.drop_hint)
        self.drop_formats = QLabel("PDF · JPG · PNG · WEBP · BMP")
        self.drop_formats.setProperty("role", "muted")
        self.drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.drop_formats)
        drop_layout.addSpacing(8)
        drop_actions = QHBoxLayout()
        drop_actions.setSpacing(8)
        self.open_pdf_button = ActionButton(variant="primary", icon=icon("pdf", "#10141D"))
        self.open_pdf_button.clicked.connect(self.open_pdf_as_project)
        self.new_button = ActionButton(icon=icon("add"))
        self.new_button.clicked.connect(self.new_project)
        self.open_button = ActionButton(icon=icon("folder"))
        self.open_button.clicked.connect(self.open_project_dialog)
        for button in (self.open_pdf_button, self.new_button, self.open_button):
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
        self.start_steps = QWidget()
        steps_layout = QHBoxLayout(self.start_steps)
        steps_layout.setContentsMargins(0, 8, 0, 8)
        steps_layout.setSpacing(16)
        self.step_labels = []
        for _ in range(4):
            label = QLabel()
            label.setProperty("role", "step")
            steps_layout.addWidget(label, 1)
            self.step_labels.append(label)
        layout.addWidget(self.start_steps)
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
        self.stack.addWidget(self.workspace)

    def _on_workspace_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        count = self.workspace.quality_warning_count
        self.quality_badge.setText(f"⚠ {count}")
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
        self.right_action.toggled.connect(self.workspace.right_tabs.parentWidget().setVisible)
        self.view_menu.addAction(self.right_action)
        self.page_info_action.setChecked(bool(self.service.config.data.get("show_page_info", False)))
        self.bottom_action.setChecked(bool(self.service.config.data.get("show_bottom", False)))
        self.focus_action = QAction(self)
        self.focus_action.setShortcut("Tab")
        self.focus_action.triggered.connect(self.toggle_focus)
        self.view_menu.addAction(self.focus_action)
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
        self.translation_menu = self.menuBar().addMenu("")
        for key in ("word_export", "word_import"):
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
        self.toolbar = self.addToolBar("")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setFixedHeight(48)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for key, glyph in (("pdf", "pdf"), ("images", "image"), ("folder", "folder"),
                           ("ocr_page", "ocr"), ("export_source", "text"),
                           ("erase_refill", "erase"), ("export_all", "export")):
            action = self.workspace.actions[key]
            action.setIcon(icon(glyph, "#10141D" if key == "erase_refill" else "#A8AFBD", 18))
            self.toolbar.addAction(action)
            if key == "erase_refill":
                button = self.toolbar.widgetForAction(action)
                button.setProperty("variant", "primary")
                button.style().unpolish(button)
                button.style().polish(button)
        self.toolbar.addSeparator()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        for key, glyph in (("previous", "previous"), ("next", "next")):
            action = self.workspace.actions[key]
            action.setIcon(icon(glyph, size=18))
            self.toolbar.addAction(action)
            self.toolbar.widgetForAction(action).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.page_counter = QLabel("— / —")
        self.page_counter.setMinimumWidth(68)
        self.page_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toolbar.addWidget(self.page_counter)
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

    def retranslate(self, *_args) -> None:
        tr = self.language.tr
        self.subtitle.setText(TAGLINE_ZH if self.language.language == "zh_CN" else TAGLINE_EN)
        self.author_footer.setText(f"Created by {AUTHOR_EN}")
        self.drop_hint.setText("将漫画拖到这里" if self.language.language == "zh_CN" else "Drop manga here")
        self.new_button.setText(tr("action.new_project"))
        self.open_button.setText(tr("action.open_project"))
        self.open_pdf_button.setText("打开 PDF" if self.language.language == "zh_CN" else "Open PDF")
        self.open_pdf_button.setToolTip("打开 PDF，并自动创建一个漫画项目。" if self.language.language == "zh_CN"
                                        else "Open a PDF and create a manga project automatically.")
        self.recent_label.setText(tr("panel.recent"))
        self.recent_empty.setText("最近打开的项目会显示在这里。" if self.language.language == "zh_CN" else
                                  "Recently opened projects appear here.")
        steps = ("导入漫画", "识别文字", "翻译与嵌字", "检查并导出") if self.language.language == "zh_CN" else (
            "Import manga", "Recognize text", "Translate & typeset", "Review & export")
        for number, (label, name) in enumerate(zip(self.step_labels, steps), 1):
            label.setText(f"{number:02d}  {name}")
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
        self.recent_menu.setTitle(tr("panel.recent"))
        self.save_action.setText(tr("action.save_project"))
        self.diagnostic_action.setText(tr("action.diagnostics"))
        self.about_action.setText("关于" if self.language.language == "zh_CN" else "About")
        self.open_log_action.setText(tr("action.open_logs"))
        self.language_actions[self.language.language].setChecked(True)
        self.workspace.retranslate()
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
            item.setToolTip(path)
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
            open_button.setToolTip(path)
            open_button.setStyleSheet("text-align: left; border: 0; padding: 3px;")
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
                action.setToolTip(path)
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
        SettingsDialog(self).exec()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def set_theme(self, mode: str) -> None:
        self.theme.set_mode(mode)
        self.update_theme()

    def update_theme(self) -> None:
        tokens = self.theme.tokens
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
                tokens["accent_text"] if key == "erase_refill" else tokens["text_secondary"], 18))
        self.refresh_recent()
        self.update()

    def new_project(self) -> None:
        dialog = NewProjectDialog(self.language, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
        try:
            self.service.open_project(path)
            self._project_opened()
        except ProjectError as exc:
            QMessageBox.critical(self, self.language.tr("dialog.project_error"), self.language.user_error(str(exc)))

    def _project_opened(self) -> None:
        self.workspace.load_project(self.service.path, self.service.connection)
        self.stack.setCurrentIndex(1)
        self.toolbar.show()
        self.setWindowTitle(f"{self.service.path.stem} — {DISPLAY_NAME}")
        self._update_toolbar_position()
        self.statusBar().showMessage(self.service.path.stem)
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
        self.workspace.unload()
        self.service.close_project()
        self.stack.setCurrentIndex(0)
        self.toolbar.hide()
        self.quality_badge.hide()
        self.refresh_recent()
        self.setWindowTitle(DISPLAY_NAME)
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
        if self.workspace.jobs:
            QMessageBox.information(self, self.language.tr("dialog.operation_running"), self.language.tr("dialog.wait_operation"))
            event.ignore()
            return
        self.workspace.unload()
        self.service.close_project()
        super().closeEvent(event)

    def _busy_changed(self, busy: bool) -> None:
        for action in getattr(self, "project_actions", []):
            action.setEnabled(not busy)
        self.backup_action.setEnabled(not busy and self.service.path is not None)
