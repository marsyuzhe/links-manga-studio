"""Page-workspace controller; business work stays in services and workers."""
from __future__ import annotations
import json
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFontDatabase
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QInputDialog,
                              QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
                              QMenu, QProgressBar, QPushButton, QSpinBox, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget)
from app.cache.image_cache import ImageCache
from app.database.database import connect
from app.importers.folder_importer import scan_files, scan_folder
from app.importers.image_importer import ImageImporter, ImportPreview
from app.pages.page_service import PageService
from app.pdf.importer import PdfImporter
from app.ocr.pipeline import ModelManager
from app.ocr.tasks import run_ocr_task
from app.ocr.review import TextBlockService
from app.tasks.service import TaskService
from app.batches.service import BatchService
from app.documents.word import WordExchange
from app.rendering.export import export_pages
from app.rendering.edits import RenderEditService
from app.images.image_loader import ImageLoader
from app.pdf.render import PdfRenderService, PREVIEW_DPI
from app.history import HistoryService
from app.workflow import WorkflowService
from .mask_editor import MaskDialog
from .font_picker import FontPicker
from app.rendering.fonts import FontCatalog
from app.rendering.fonts import FontPreferences
from app.rendering.font_match import recommend
from app.rendering.layout import fit_layout
from app.styles.project_styles import ProjectStyleService, ROLES
from app.quality.checker import QualityChecker
from .project_styles import ProjectStylesDialog
from .quality_dialog import QualityDialog
from app.config import config_dir
from .canvas import ComicCanvas
from .page_panel import PageListModel, PageRowDelegate
from .workers import ImageWorker, Job
from .icons import icon
from .components import ActionButton, SectionHeader


class Workspace(QWidget):
    status_changed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, config, language, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.language = language
        self.project: Path | None = None
        self.pages_service: PageService | None = None
        self.cache = ImageCache(config.image_cache_mb * 1024 * 1024)
        self.thumbnail_cache = ImageCache(16 * 1024 * 1024)
        self.image_worker = self.thumb_worker = None
        self.jobs: list[Job] = []
        self._drop_queue: list[Path | list[Path]] = []
        self.generation = 0
        self.thumbnail_generation = 0
        self.current_row = -1
        self.current_id = None
        self.model = PageListModel(language, self)
        self.panel = QListView()
        self.panel.setModel(self.model)
        self.page_delegate = PageRowDelegate(self.panel)
        self.panel.setItemDelegate(self.page_delegate)
        self.panel.setUniformItemSizes(True)
        self.panel.setIconSize(QSize(64, 88))
        self.panel.setMinimumWidth(220)
        self.panel.setAccessibleName(self.language.tr("panel.pages"))
        self.panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.panel.customContextMenuRequested.connect(self._page_context_menu)
        self.batch_list = QListWidget()
        self.ocr_list = QListWidget()
        self.ocr_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.ocr_search = QLineEdit()
        self.ocr_filter = QComboBox()
        self.ocr_filter.addItems(["all", "untranslated", "translated", "low confidence", "not typeset", "overflow"])
        self.ocr_panel = QWidget()
        ocr_layout = QVBoxLayout(self.ocr_panel)
        ocr_layout.setContentsMargins(12, 12, 12, 12)
        ocr_layout.setSpacing(8)
        ocr_layout.addWidget(self.ocr_search)
        ocr_layout.addWidget(self.ocr_filter)
        ocr_layout.addWidget(self.ocr_list, 1)
        self.ocr_empty = QLabel()
        self.ocr_empty.setProperty("role", "muted")
        self.ocr_empty.setWordWrap(True)
        ocr_layout.addWidget(self.ocr_empty)
        self.ocr_empty_button = ActionButton(icon=icon("ocr"))
        self.ocr_empty_button.clicked.connect(self.ocr_current_page)
        ocr_layout.addWidget(self.ocr_empty_button)
        self.ocr_search.textChanged.connect(self._refresh_ocr_list)
        self.ocr_filter.currentIndexChanged.connect(self._refresh_ocr_list)
        self.project_list = QListWidget()
        self.left_tabs = QTabWidget()
        for widget, title in ((self.panel, "Pages"), (self.ocr_panel, "OCR Text"),
                              (self.batch_list, "Batches"), (self.project_list, "Project")):
            self.left_tabs.addTab(widget, title)
        self.left_tabs.setMinimumWidth(220)
        self.left_tabs.setProperty("role", "panel")
        self.ocr_list.currentRowChanged.connect(self._ocr_list_selected)
        self.canvas = ComicCanvas()
        self.canvas.setAccessibleName(self.language.tr("panel.workspace_empty"))
        self.inspector = QLabel(self.language.tr("panel.inspector"))
        self.inspector.setMinimumWidth(190)
        self.inspector.setWordWrap(True)
        self.inspector.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.inspector.setTextFormat(Qt.TextFormat.PlainText)
        self.selected_block = None
        self._loading_block = False
        self.quality_warning_count = 0
        self.copied_style = None
        self.block_source = QTextEdit()
        self.block_source.setMaximumHeight(90)
        self.block_translation = QTextEdit()
        self.block_translation.setMinimumHeight(120)
        self.block_translation.setMaximumHeight(200)
        self.translation_timer = QTimer(self)
        self.translation_timer.setSingleShot(True)
        self.translation_timer.setInterval(600)
        self.translation_timer.timeout.connect(self._save_translation_debounced)
        self.block_translation.textChanged.connect(self._schedule_translation_save)
        self.block_notes = QTextEdit()
        self.block_notes.setMaximumHeight(70)
        self.block_notes.textChanged.connect(self._schedule_translation_save)
        self.translation_status = QLabel()
        self.translation_source_summary = QLabel()
        self.translation_source_summary.setWordWrap(True)
        self.translation_role = QLabel()
        self.block_order = QSpinBox()
        self.block_order.setRange(1, 100000)
        self.geometry_inputs = {}
        for key in ("x", "y", "width", "height", "rotation"):
            field = QDoubleSpinBox()
            field.setRange(-360 if key == "rotation" else 0, 360 if key == "rotation" else 100000)
            field.setDecimals(1)
            self.geometry_inputs[key] = field
        self.font_field = QLineEdit()
        self.font_picker_button = QPushButton()
        self.font_picker_button.clicked.connect(self.choose_font)
        self.font_size_field = QSpinBox()
        self.font_size_field.setRange(8, 300)
        self.min_font_size_field = QSpinBox()
        self.min_font_size_field.setRange(6, 300)
        self.color_field = QLineEdit()
        self.stroke_color_field = QLineEdit()
        self.stroke_width_field = QDoubleSpinBox()
        self.stroke_width_field.setRange(0, 30)
        self.font_weight_field = QSpinBox()
        self.font_weight_field.setRange(100, 900)
        self.font_weight_field.setSingleStep(100)
        self.padding_field = QSpinBox()
        self.padding_field.setRange(0, 200)
        self.line_spacing_field = QDoubleSpinBox()
        self.line_spacing_field.setRange(.5, 3)
        self.line_spacing_field.setSingleStep(.05)
        self.letter_spacing_field = QDoubleSpinBox()
        self.letter_spacing_field.setRange(-10, 30)
        self.alignment_field = QComboBox()
        for value in ("left", "center", "right"):
            self.alignment_field.addItem(value, value)
        self.vertical_alignment_field = QComboBox()
        for value in ("top", "center", "bottom"):
            self.vertical_alignment_field.addItem(value, value)
        self.writing_mode_field = QComboBox()
        for value in ("horizontal", "vertical"):
            self.writing_mode_field.addItem(value, value)
        self.auto_fit_field = QCheckBox()
        self.auto_fit_field.setChecked(True)
        self.fit_status_label = QLabel()
        self.style_role = QComboBox()
        for role in ROLES:
            self.style_role.addItem(role, role)
        self.style_role.currentIndexChanged.connect(self._role_changed)
        self.style_inheritance = QLabel()
        self.style_apply_to = QComboBox()
        for scope in ("block", "page", "batch", "project"):
            self.style_apply_to.addItem(scope, scope)
        self.style_apply_button = QPushButton()
        self.style_apply_button.clicked.connect(self.apply_style)
        self.style_reset_button = QPushButton()
        self.style_reset_button.clicked.connect(self.reset_style)
        self.auto_fit_button = QPushButton()
        self.auto_fit_button.clicked.connect(self.refresh_auto_fit)
        self.erase_mode = QComboBox()
        for mode in ("none", "fill", "telea", "ns"):
            self.erase_mode.addItem(mode)
        self.save_block_button = QPushButton()
        self.save_block_button.clicked.connect(self.save_block)
        self.erase_refill_button = QPushButton()
        self.erase_refill_button.clicked.connect(self.erase_and_refill_current)
        self.erase_only_button = QPushButton()
        self.erase_only_button.clicked.connect(self.erase_selected_block)
        self.fill_only_button = QPushButton()
        self.fill_only_button.clicked.connect(self.fill_selected_block)
        self.restore_erase_button = QPushButton()
        self.restore_erase_button.clicked.connect(self.restore_selected_block)
        self.source_confidence = QLabel()
        self.delete_block_button = QPushButton()
        self.delete_block_button.clicked.connect(self.delete_block)
        self.duplicate_block_button = QPushButton()
        self.duplicate_block_button.clicked.connect(self.duplicate_block)
        self.copy_style_button = QPushButton()
        self.copy_style_button.clicked.connect(self.copy_style)
        self.paste_style_button = QPushButton()
        self.paste_style_button.clicked.connect(self.paste_style)
        self.mask_button = QPushButton()
        self.mask_button.clicked.connect(self.edit_mask)
        self.block_id_label = QLabel()
        self.review_labels = {key: QLabel() for key in ("source", "translation", "notes", "order",
                                                    "x", "y", "width", "height", "rotation", "font", "size", "color", "erase")}
        self.style_labels = {key: QLabel() for key in ("role", "stroke_color", "stroke_width", "font_weight",
            "apply_to", "min_size", "auto_fit", "alignment", "padding", "line_spacing",
            "letter_spacing", "vertical_alignment", "writing_mode")}
        self.right_tabs = QTabWidget()
        self.block_editor = self.right_tabs
        properties = QWidget()
        form = QFormLayout(properties)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(8)
        form.addRow(self.block_id_label)
        for key, field in self.geometry_inputs.items():
            form.addRow(self.review_labels[key], field)
        form.addRow(self.duplicate_block_button)
        form.addRow(self.delete_block_button)
        form.addRow(self.copy_style_button)
        form.addRow(self.paste_style_button)
        form.addRow(self.save_block_button)
        source_tab = QWidget()
        source_form = QFormLayout(source_tab)
        source_form.setContentsMargins(12, 16, 12, 12)
        source_form.setSpacing(8)
        source_form.addRow(self.review_labels["source"], self.block_source)
        source_form.addRow(self.source_confidence)
        source_form.addRow(self.review_labels["order"], self.block_order)
        translation_tab = QWidget()
        translation_form = QVBoxLayout(translation_tab)
        translation_form.setContentsMargins(12, 16, 12, 12)
        translation_form.setSpacing(8)
        self.translation_role.setProperty("role", "muted")
        self.translation_source_summary.setProperty("role", "section")
        translation_form.addWidget(self.translation_role)
        translation_form.addWidget(self.translation_source_summary)
        translation_form.addSpacing(8)
        translation_form.addWidget(self.review_labels["translation"])
        translation_form.addWidget(self.block_translation)
        translation_form.addWidget(self.review_labels["notes"])
        translation_form.addWidget(self.block_notes)
        translation_form.addStretch(1)
        self.erase_refill_button.setProperty("variant", "primary")
        self.erase_refill_button.setMinimumHeight(40)
        self.erase_refill_button.setIcon(icon("erase", "#10141D"))
        translation_form.addWidget(self.erase_refill_button)
        translation_form.addWidget(self.fill_only_button)
        self.translation_status.setProperty("role", "badge")
        translation_form.addWidget(self.translation_status)
        erase_tab = QWidget()
        erase_form = QFormLayout(erase_tab)
        erase_form.setContentsMargins(12, 16, 12, 12)
        erase_form.setSpacing(8)
        erase_form.addRow(self.review_labels["erase"], self.erase_mode)
        erase_form.addRow(self.erase_only_button)
        erase_form.addRow(self.restore_erase_button)
        erase_form.addRow(self.mask_button)
        style_tab = QWidget()
        self.style_form = QFormLayout(style_tab)
        self.style_form.setContentsMargins(12, 16, 12, 12)
        self.style_form.setSpacing(8)
        self.style_form.addRow(self.style_inheritance)
        self.style_form.addRow(self.style_labels["role"], self.style_role)
        self.style_form.addRow(self.review_labels["font"], self.font_field)
        self.style_form.addRow(self.font_picker_button)
        self.style_form.addRow(self.review_labels["color"], self.color_field)
        self.style_form.addRow(self.style_labels["stroke_color"], self.stroke_color_field)
        self.style_form.addRow(self.style_labels["stroke_width"], self.stroke_width_field)
        self.style_form.addRow(self.style_labels["font_weight"], self.font_weight_field)
        self.style_form.addRow(self.style_labels["apply_to"], self.style_apply_to)
        self.style_form.addRow(self.style_apply_button)
        self.style_form.addRow(self.style_reset_button)
        typeset_tab = QWidget()
        self.typeset_form = QFormLayout(typeset_tab)
        self.typeset_form.setContentsMargins(12, 16, 12, 12)
        self.typeset_form.setSpacing(8)
        self.typeset_form.addRow(self.review_labels["size"], self.font_size_field)
        self.typeset_form.addRow(self.style_labels["min_size"], self.min_font_size_field)
        self.typeset_form.addRow(self.style_labels["auto_fit"], self.auto_fit_field)
        self.typeset_form.addRow(self.style_labels["alignment"], self.alignment_field)
        self.typeset_form.addRow(self.style_labels["padding"], self.padding_field)
        self.typeset_form.addRow(self.style_labels["line_spacing"], self.line_spacing_field)
        self.typeset_form.addRow(self.style_labels["letter_spacing"], self.letter_spacing_field)
        self.typeset_form.addRow(self.style_labels["vertical_alignment"], self.vertical_alignment_field)
        self.typeset_form.addRow(self.style_labels["writing_mode"], self.writing_mode_field)
        self.typeset_form.addRow(self.auto_fit_button)
        self.typeset_form.addRow(self.fit_status_label)
        for widget, title in ((translation_tab, "Translation"), (style_tab, "Style"),
                              (typeset_tab, "Typeset"), (source_tab, "Original"),
                              (erase_tab, "Erase"), (properties, "Advanced")):
            self.right_tabs.addTab(widget, title)
        inspector_panel = QWidget()
        inspector_panel.setProperty("role", "panel")
        inspector_panel.setMinimumWidth(300)
        inspector_layout = QVBoxLayout(inspector_panel)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(0)
        self.inspector_header = SectionHeader()
        self.inspector_header.setContentsMargins(12, 12, 12, 2)
        self.inspector_header.setText("选择文字框" if self.language.language == "zh_CN" else "Select a text region")
        inspector_layout.addWidget(self.inspector_header)
        self.inspector_state = QLabel()
        self.inspector_state.setProperty("role", "muted")
        self.inspector_state.setContentsMargins(12, 0, 12, 12)
        self.inspector_state.setText("点击漫画中的文字区域开始编辑" if self.language.language == "zh_CN" else
                                     "Click a text region on the page to edit")
        inspector_layout.addWidget(self.inspector_state)
        self.inspector.hide()
        inspector_layout.addWidget(self.inspector)
        inspector_layout.addWidget(self.right_tabs, 1)
        splitter = QSplitter()
        self.main_splitter = splitter
        for widget in (self.left_tabs, self.canvas, inspector_panel):
            splitter.addWidget(widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 760, 320])
        self.progress = QProgressBar()
        self.progress.hide()
        self.progress_label = QLabel()
        self.progress_label.hide()
        self._job_title = ""
        self._last_progress = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        work_row = QHBoxLayout()
        work_row.setContentsMargins(0, 0, 0, 0)
        work_row.setSpacing(0)
        self.tool_rail = QWidget()
        self.tool_rail.setProperty("role", "rail")
        self.tool_rail.setFixedWidth(48)
        self.rail_layout = QVBoxLayout(self.tool_rail)
        self.rail_layout.setContentsMargins(4, 8, 4, 8)
        self.rail_layout.setSpacing(4)
        work_row.addWidget(self.tool_rail)
        work_row.addWidget(splitter, 1)
        layout.addLayout(work_row, 1)
        self.bottom_tabs = QTabWidget()
        task_tab = QWidget()
        task_layout = QVBoxLayout(task_tab)
        task_layout.addWidget(self.progress_label)
        task_layout.addWidget(self.progress)
        self.log_label = QPlainTextEdit()
        self.log_label.setReadOnly(True)
        self.export_label = QLabel("No export running")
        self.bottom_tabs.addTab(task_tab, "Tasks")
        self.bottom_tabs.addTab(self.log_label, "Logs")
        self.bottom_tabs.addTab(self.export_label, "Export")
        quality_tab = QWidget()
        quality_layout = QVBoxLayout(quality_tab)
        quality_layout.setContentsMargins(12, 8, 12, 8)
        self.quality_summary = QLabel()
        self.quality_summary.setProperty("role", "muted")
        self.quality_list = QListWidget()
        self.quality_list.itemDoubleClicked.connect(lambda item: self._locate_quality_issue(
            item.data(Qt.ItemDataRole.UserRole)))
        quality_layout.addWidget(self.quality_summary)
        quality_layout.addWidget(self.quality_list, 1)
        self.bottom_tabs.addTab(quality_tab, "Quality")
        self.bottom_tabs.currentChanged.connect(self._bottom_tab_changed)
        self.bottom_tabs.setMaximumHeight(200)
        self.bottom_tabs.hide()
        layout.addWidget(self.bottom_tabs)
        self.thumbnail_timer = QTimer(self)
        self.thumbnail_timer.setSingleShot(True)
        self.thumbnail_timer.setInterval(60)
        self.thumbnail_timer.timeout.connect(self.request_thumbnails)
        self.panel.verticalScrollBar().valueChanged.connect(lambda: self.thumbnail_timer.start())
        self.panel.selectionModel().currentChanged.connect(lambda current, previous: self.select_page(current.row()))
        self.canvas.zoom_changed.connect(lambda value: self.update_status())
        self.canvas.block_selected.connect(self.select_block)
        self.canvas.block_edit_requested.connect(self.edit_translation_on_canvas)
        self.canvas.block_double_clicked.connect(self.focus_translation_editor)
        self.canvas.block_changed.connect(self._canvas_block_changed)
        self.canvas.block_context_requested.connect(self._block_context_menu)
        self.actions: dict[str, QAction] = {}
        definitions = [
            ("images", "action.import_images", self.import_images, ""),
            ("folder", "action.import_folder", self.import_folder, ""),
            ("pdf", "action.import_pdf", self.import_pdf, ""),
            ("export_source", "action.export_source", self.export_source_dialog, ""),
            ("erase_quick", "action.erase_quick", self.erase_quick_dialog, ""),
            ("erase_refill", "action.erase_refill", self.erase_and_refill_current, "Ctrl+Return"),
            ("fill_translation", "action.fill_translation", self.enable_text_tool, ""),
            ("ocr_page", "action.ocr_page", self.ocr_current_page, ""),
            ("ocr_all", "action.ocr_all", self.ocr_all_pages, ""),
            ("ocr_resume", "action.ocr_resume", self.resume_ocr, ""),
            ("models", "action.models", self.show_models, ""),
            ("batches", "action.create_batches", self.create_batches, ""),
            ("project_styles", "style.project_title", self.show_project_styles, ""),
            ("replace_fonts", "font.replace_missing", self.replace_missing_fonts, ""),
            ("quality_check", "quality.title", self.show_quality_check, ""),
            ("word_export", "action.word_export", self.export_word, ""),
            ("word_import", "action.word_import", self.import_word, ""),
            ("export_page", "action.export_page", self.export_current_page, ""),
            ("export_batch", "action.export_batch", self.export_current_batch, ""),
            ("export_all", "action.export_all", self.export_all_pages, ""),
            ("export_resume", "action.export_resume", self.resume_export, ""),
            ("undo", "action.undo", self.undo, "Ctrl+Z"),
            ("redo", "action.redo", self.redo, "Ctrl+Y"),
            ("copy_style", "review.copy_style", self.copy_style, "Ctrl+Shift+C"),
            ("paste_style", "review.paste_style", self.paste_style, "Ctrl+Shift+V"),
            ("duplicate_block", "review.duplicate", self.duplicate_block, ""),
            ("delete_block", "review.delete", self.delete_block, ""),
            ("previous", "action.previous_page", lambda: self.navigate(-1), "PgUp"),
            ("next", "action.next_page", lambda: self.navigate(1), "PgDown"),
            ("fit", "action.fit_window", self.canvas.fit, "Ctrl+0"),
            ("actual", "action.actual_size", lambda: self.canvas.set_zoom(1), "Ctrl+1"),
            ("zoom_in", "action.zoom_in", lambda: self.canvas.zoom_by(1.2), "+"),
            ("zoom_out", "action.zoom_out", lambda: self.canvas.zoom_by(1/1.2), "-"),
            ("goto", "action.go_to_page", self.go_to_page, "Ctrl+G"),
            ("up", "action.move_up", lambda: self.move_page(-1), ""),
            ("down", "action.move_down", lambda: self.move_page(1), ""),
            ("relocate", "action.relocate", self.relocate, ""),
        ]
        self.action_keys = {}
        for key, text_key, handler, shortcut in definitions:
            action = QAction(self.language.tr(text_key), self)
            action.triggered.connect(handler)
            if shortcut:
                action.setShortcut(shortcut)
            self.addAction(action)
            self.actions[key] = action
            self.action_keys[key] = text_key
        self.actions["fill_translation"].setCheckable(True)
        self._build_tool_rail()
        self.ocr_search.setPlaceholderText(self.language.tr("panel.search_ocr"))
        self.update_actions()

    def update_theme(self, tokens) -> None:
        self.model.set_theme(tokens)
        self.page_delegate.tokens = tokens
        self.panel.viewport().update()
        self.canvas.set_theme(tokens)
        for name, button in self.rail_buttons.items():
            button.setIcon(icon(name, tokens["text_secondary"], 20))
        self.erase_refill_button.setIcon(icon("erase", tokens["accent_text"]))
        self.update()

    def _build_tool_rail(self) -> None:
        self.rail_buttons = {}
        for key, glyph, handler in (
            ("pointer", "pointer", lambda: self._activate_rail("pointer")),
            ("hand", "hand", lambda: self._activate_rail("hand")),
            ("text", "text", lambda: self._activate_rail("text")),
            ("erase", "erase", self.erase_selected_block),
            ("mask", "mask", self.edit_mask),
            ("zoom", "zoom", lambda: self.canvas.zoom_by(1.2)),
        ):
            button = ActionButton(variant="rail", icon=icon(glyph, size=20))
            button.setFixedSize(40, 40)
            button.clicked.connect(handler)
            button.setCheckable(key in ("pointer", "hand", "text"))
            self.rail_layout.addWidget(button)
            self.rail_buttons[key] = button
        self.rail_buttons["pointer"].setChecked(True)
        self.rail_layout.addStretch(1)

    def _block_context_menu(self, block_id: str, position) -> None:
        self.select_block(block_id)
        menu = QMenu(self)
        for title, handler in (
            (self.language.tr("review.translation"), lambda: self.focus_translation_editor(block_id)),
            (self.language.tr("action.erase_only"), self.erase_selected_block),
            (self.language.tr("action.erase_refill"), self.erase_and_refill_current),
            (self.language.tr("style.auto_fit_now"), self.refresh_auto_fit),
            (self.language.tr("review.copy_style"), self.copy_style),
            (self.language.tr("review.paste_style"), self.paste_style),
            (self.language.tr("review.delete"), self.delete_block),
        ):
            menu.addAction(title, handler)
        menu.exec(position)

    def _page_context_menu(self, position) -> None:
        index = self.panel.indexAt(position)
        if not index.isValid():
            return
        self.panel.setCurrentIndex(index)
        menu = QMenu(self)
        for title, handler in (
            (self.language.tr("action.ocr_page"), self.ocr_current_page),
            (self.language.tr("action.export_page"), self.export_current_page),
            (self.language.tr("quality.title"), self.show_quality_check),
        ):
            menu.addAction(title, handler)
        menu.exec(self.panel.viewport().mapToGlobal(position))

    def _activate_rail(self, key: str) -> None:
        for name in ("pointer", "hand", "text"):
            self.rail_buttons[name].setChecked(name == key)
        self.canvas.set_hand_tool(key == "hand")
        self.actions["fill_translation"].setChecked(key == "text")
        self.canvas.text_tool = key == "text"
        if key == "text":
            self.enable_text_tool()

    def _bottom_tab_changed(self, index: int) -> None:
        if index == 1:
            path = getattr(self.window(), "log_path", config_dir() / "logs" / "app.log")
            self.log_label.setPlainText("\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
                                        if path.is_file() else str(path))

    def retranslate(self) -> None:
        tr = self.language.tr
        for key, action in self.actions.items():
            action.setText(tr(self.action_keys[key]))
        self.panel.setAccessibleName(tr("panel.pages"))
        for index, key in enumerate(("panel.pages", "panel.ocr_text", "panel.batches", "panel.project")):
            self.left_tabs.setTabText(index, tr(key))
        for key, tip in (("pointer", "Pointer"), ("hand", "Hand · Space + drag"),
                         ("text", tr("action.fill_translation")), ("erase", tr("action.erase_only")),
                         ("mask", tr("review.mask")), ("zoom", tr("action.zoom_in"))):
            self.rail_buttons[key].setToolTip(tip)
        self.ocr_empty.setText("当前页还没有识别文字。" if self.language.language == "zh_CN" else
                               "No text recognized on this page yet.")
        self.ocr_empty_button.setText(tr("action.ocr_page"))
        for index, key in enumerate(("panel.translation", "panel.style", "panel.typeset", "panel.original", "panel.erase", "panel.advanced")):
            self.right_tabs.setTabText(index, tr(key))
        for key, label in self.style_labels.items():
            label.setText(tr("style." + key))
        for index, role in enumerate(ROLES):
            self.style_role.setItemText(index, tr("style.role_" + role))
        for control in (self.alignment_field, self.vertical_alignment_field, self.writing_mode_field):
            for index in range(control.count()):
                control.setItemText(index, tr("style." + control.itemData(index)))
        for index in range(self.style_apply_to.count()):
            self.style_apply_to.setItemText(index, tr("style.scope_" + self.style_apply_to.itemData(index)))
        self.style_apply_button.setText(tr("style.apply"))
        self.style_reset_button.setText(tr("style.reset"))
        self.auto_fit_button.setText(tr("style.auto_fit_now"))
        self.ocr_search.setPlaceholderText(tr("panel.search_ocr"))
        for index, key in enumerate(("filter.all", "filter.untranslated", "filter.translated", "filter.low_confidence", "filter.not_typeset", "filter.overflow")):
            self.ocr_filter.setItemText(index, tr(key))
        for index, key in enumerate(("panel.tasks", "panel.logs", "panel.export")):
            self.bottom_tabs.setTabText(index, tr(key))
        self.bottom_tabs.setTabText(3, tr("quality.title"))
        self.canvas.setAccessibleName(tr("panel.canvas"))
        self.model.retranslate()
        for key, label in self.review_labels.items():
            label.setText(tr(f"review.{key}"))
        self.save_block_button.setText(tr("review.save"))
        self.erase_refill_button.setText(tr("action.erase_refill"))
        self.erase_only_button.setText(tr("action.erase_only"))
        self.fill_only_button.setText(tr("action.fill_only"))
        self.restore_erase_button.setText(tr("action.restore_erase"))
        self.erase_refill_button.setToolTip(tr("tooltip.erase_refill"))
        self.actions["export_source"].setToolTip(tr("tooltip.export_source"))
        self.actions["erase_refill"].setToolTip(tr("tooltip.erase_refill"))
        self.delete_block_button.setText(tr("review.delete"))
        self.duplicate_block_button.setText(tr("review.duplicate"))
        self.copy_style_button.setText(tr("review.copy_style"))
        self.paste_style_button.setText(tr("review.paste_style"))
        self.mask_button.setText(tr("review.mask"))
        self.font_picker_button.setText(tr("review.search_fonts"))
        if self.progress.isVisible():
            if self._last_progress:
                value, total, text = self._last_progress
                self.progress_label.setText(tr("status.job_progress", task=self.language.progress_text(text),
                                               value=value, total=total))
            else:
                self.progress_label.setText(tr(self._job_title))
        if self.current_id:
            self.update_status()
            if not self.canvas._has_image:
                page = self.model.pages[self.current_row]
                self.canvas.message(tr("status.missing_canvas") if page["status"] == "missing" else
                                    tr("status.broken_canvas") if page["status"] == "broken" else tr("status.loading"))
        elif self.project:
            self.canvas.message(tr("panel.workspace_empty"))
            self.inspector.setText(tr("panel.inspector"))
        self.update_actions()

    def load_project(self, project: Path, connection) -> None:
        self.unload()
        self.project = project
        self.pages_service = PageService(connection, project)
        self.image_worker = ImageWorker(project, self.cache)
        self.thumb_worker = ImageWorker(project, self.thumbnail_cache, thumbnail=True)
        self.image_worker.signals.ready.connect(self.image_ready)
        self.thumb_worker.signals.ready.connect(self.thumbnail_ready)
        self.reload_pages()
        self._check_project_fonts()
        def health(progress, cancel):
            ImageImporter(project).recover()
            db = connect(project / "project.sqlite3")
            try:
                TaskService(db).recover_interrupted()
                return PageService(db, project).health_check()
            finally:
                db.close()
        if self.model.pages or (project / "sources" / ".imports").exists():
            self.run_job(health, lambda result: self.reload_pages(), "status.checking")

    def unload(self) -> None:
        self._drop_queue.clear()
        self.generation += 1
        self.thumbnail_generation += 1
        self.thumbnail_timer.stop()
        for worker in (self.image_worker, self.thumb_worker):
            if worker:
                worker.signals.ready.disconnect()
                worker.stop()
        self.image_worker = self.thumb_worker = None
        self.cache.clear()
        self.thumbnail_cache.clear()
        self.model.set_pages([])
        self.project = self.pages_service = None
        self.current_row = -1
        self.current_id = None
        self.selected_block = None
        self.canvas.text_tool = False
        self.actions["fill_translation"].setChecked(False)
        self.ocr_list.clear()
        self.canvas.message(self.language.tr("panel.workspace_empty"))
        self.update_actions()

    def reload_pages(self, select_id: str | None = None) -> None:
        self.quality_warning_count = 0
        pages = self.pages_service.list_pages()
        selected = select_id or self.current_id
        self.model.set_pages(pages)
        self._refresh_side_panels()
        if pages:
            row = next((i for i, p in enumerate(pages) if p["id"] == selected), 0)
            self.panel.setCurrentIndex(self.model.index(row))
        else:
            self.current_row = -1
            self.canvas.message(self.language.tr("panel.workspace_empty"))
        self.thumbnail_timer.start()
        self.update_actions()

    def _refresh_side_panels(self) -> None:
        self.batch_list.clear()
        self.project_list.clear()
        if not self.pages_service:
            self.ocr_list.clear()
            return
        for batch in BatchService(self.pages_service.connection).list_batches():
            self.batch_list.addItem(f"Batch {batch['batch_number']} · {batch['page_count']} pages")
        self.project_list.addItem(str(self.project))
        self.project_list.addItem(f"{len(self.model.pages)} pages")
        self._refresh_ocr_list()

    def _refresh_ocr_list(self) -> None:
        self.ocr_list.clear()
        if not self.pages_service or not self.current_id:
            self.ocr_empty.show()
            self.ocr_empty_button.setEnabled(False)
            return
        review = TextBlockService(self.pages_service.connection)
        query = self.ocr_search.text().strip().casefold()
        mode = self.ocr_filter.currentIndex()
        for block in review.for_page(self.current_id):
            translated = review.translation(block["id"])
            has_translation = bool(translated and translated["text"].strip())
            erased = block.get("erase_status") == "erased"
            if (mode == 1 and has_translation) or (mode == 2 and not has_translation) or (mode == 3 and float(block.get("ocr_confidence") or 0) >= .75):
                continue
            if mode == 4 and (not has_translation or block.get("typeset_status") == "ready"):
                continue
            overflow = False
            if mode == 5:
                if not has_translation:
                    continue
                style = ProjectStyleService(self.pages_service.connection).resolve(block)
                x0, y0, x1, y1 = json.loads(block["bbox_json"])
                overflow = fit_layout(translated["text"], style, x1-x0, y1-y0).status == "overflow"
                if not overflow:
                    continue
            if query and query not in (block["text_uid"] + block["source_text"] +
                                       (translated["text"] if translated else "")).casefold():
                continue
            status = ("E" if erased else "○") + ("✓" if has_translation else "·") + ("!" if overflow else "")
            confidence = round(100 * float(block.get("ocr_confidence") or 0))
            identifier = "" if self.model.simple_mode else block["text_uid"] + "  "
            self.ocr_list.addItem(f"{status} {identifier}{confidence}%  {block['source_text'][:38]}")
            self.ocr_list.item(self.ocr_list.count()-1).setData(Qt.ItemDataRole.UserRole, block["id"])
        self.ocr_empty.setVisible(self.ocr_list.count() == 0)
        self.ocr_empty_button.setVisible(self.ocr_list.count() == 0)
        self.ocr_empty_button.setEnabled(bool(self.current_id))

    def _ocr_list_selected(self, row: int) -> None:
        if row >= 0:
            block_id = self.ocr_list.item(row).data(Qt.ItemDataRole.UserRole)
            if block_id:
                self._selecting_from_ocr = True
                try:
                    self.select_block(block_id)
                finally:
                    self._selecting_from_ocr = False

    def select_page(self, row: int) -> None:
        if not self.project or not 0 <= row < len(self.model.pages):
            return
        if self.translation_timer.isActive():
            self._save_translation_debounced()
        self.current_row = row
        page = self.model.pages[row]
        self.current_id = page["id"]
        self.selected_block = None
        self.inspector_header.setText("选择文字框" if self.language.language == "zh_CN" else "Select a text region")
        self.inspector_state.setText("点击漫画中的文字区域开始编辑" if self.language.language == "zh_CN" else
                                     "Click a text region on the page to edit")
        self._refresh_ocr_list()
        self.generation += 1
        self.canvas.message(self.language.tr("status.loading") + "…")
        # Replace pending work: current first, then at most two neighbours.
        nearby = [page] + [self.model.pages[i] for i in (row+1, row-1) if 0 <= i < len(self.model.pages)]
        self.image_worker.request(self.generation, nearby)
        self.update_status()
        self.update_actions()
        self.thumbnail_timer.start()

    def image_ready(self, generation: int, page_id: str, image, error: str) -> None:
        if generation != self.generation or not self.project:
            return
        self.pages_service.set_status(page_id, error or "ready")
        for page in self.model.pages:
            if page["id"] == page_id:
                page["status"] = error or "ready"
                break
        if page_id != self.current_id:
            return
        if error:
            self.canvas.message(self.language.tr("status.missing_canvas" if error == "missing" else "status.broken_canvas"))
        else:
            self.canvas.show_image(page_id, image)
            page = self.model.pages[self.current_row]
            blocks = TextBlockService(self.pages_service.connection).for_page(page_id)
            self.canvas.show_blocks(blocks, page["width"], page["height"])
            if self.selected_block:
                self.canvas.select_block(self.selected_block)
            self._refresh_ocr_list()
        self.update_status()

    def select_block(self, block_id: str) -> None:
        if not self.pages_service or not self.current_id:
            return
        if self.selected_block != block_id and self.translation_timer.isActive():
            self._save_translation_debounced()
        review = TextBlockService(self.pages_service.connection)
        block = next((item for item in review.for_page(self.current_id) if item["id"] == block_id), None)
        if block is None:
            return
        self.selected_block = block_id
        self._loading_block = True
        self.update_actions()
        translation = review.translation(block_id)
        self.block_id_label.setText("" if self.model.simple_mode else block["text_uid"])
        self.inspector_header.setText(self.language.tr("style.role_" + (block.get("style_role") or "speech")))
        self.inspector_state.setText(("OCR ✓" if block.get("ocr_confidence") is not None else "OCR —") +
                                     ("  ·  " + ("已翻译" if self.language.language == "zh_CN" else "Translated")
                                      if translation and translation["text"].strip() else "") +
                                     ("  ·  " + ("已擦除" if self.language.language == "zh_CN" else "Erased")
                                      if block.get("erase_status") == "erased" else ""))
        self.translation_source_summary.setText(block["source_text"][:120])
        self.source_confidence.setText(self.language.tr("review.confidence", value=round(100 * float(block.get("ocr_confidence") or 0))))
        self.block_source.setPlainText(block["source_text"])
        self.block_translation.setPlainText(translation["text"] if translation else "")
        self.block_notes.setPlainText(translation["notes"] if translation else "")
        self.block_order.setValue(block["reading_order"])
        x0, y0, x1, y1 = json.loads(block["bbox_json"])
        for key, value in (("x", x0), ("y", y0), ("width", x1-x0), ("height", y1-y0),
                           ("rotation", block["rotation"])):
            self.geometry_inputs[key].setValue(value)
        legacy_style = {}
        if block["style_id"]:
            row = self.pages_service.connection.execute("SELECT settings_json FROM styles WHERE id=?",
                                                        (block["style_id"],)).fetchone()
            legacy_style = json.loads(row[0]) if row else {}
        style_service = ProjectStyleService(self.pages_service.connection)
        style = style_service.resolve(block, legacy_style)
        role = block.get("style_role") or "speech"
        self.style_role.setCurrentIndex(max(0, self.style_role.findData(role)))
        self.translation_role.setText(self.language.tr("style.role_" + role))
        customized = bool(json.loads(block.get("style_override_json") or "{}") or block["style_id"])
        self.style_inheritance.setText(self.language.tr("style.custom" if customized else "style.inherited"))
        self.font_field.setText(style.get("font", "Microsoft YaHei"))
        self.font_size_field.setValue(int(style.get("max_size", 72)))
        self.min_font_size_field.setValue(int(style.get("min_size", 18)))
        self.color_field.setText(style.get("color", "#000000"))
        self.stroke_color_field.setText(style.get("stroke", "#ffffff"))
        self.stroke_width_field.setValue(float(style.get("stroke_width", 0)))
        self.font_weight_field.setValue(int(style.get("font_weight", 400)))
        self.padding_field.setValue(int(style.get("padding", 8)))
        self.line_spacing_field.setValue(float(style.get("line_spacing", 1)))
        self.letter_spacing_field.setValue(float(style.get("letter_spacing", 0)))
        self.alignment_field.setCurrentIndex(max(0, self.alignment_field.findData(style.get("alignment", "center"))))
        self.vertical_alignment_field.setCurrentIndex(max(0, self.vertical_alignment_field.findData(style.get("vertical_alignment", "center"))))
        self.writing_mode_field.setCurrentIndex(max(0, self.writing_mode_field.findData(style.get("writing_mode", "horizontal"))))
        self.auto_fit_field.setChecked(bool(style.get("auto_fit", True)))
        erase = json.loads(block["erase_data_json"])
        self.erase_mode.setCurrentText(erase.get("mode", "none"))
        self._loading_block = False
        self.refresh_auto_fit()
        self.right_tabs.setCurrentIndex(0)
        self.canvas.select_block(block_id)
        if not getattr(self, "_selecting_from_ocr", False):
            for index in range(self.ocr_list.count()):
                if self.ocr_list.item(index).data(Qt.ItemDataRole.UserRole) == block_id:
                    self.ocr_list.blockSignals(True)
                    self.ocr_list.setCurrentRow(index)
                    self.ocr_list.blockSignals(False)
                    break

    def save_block(self) -> None:
        if not self.selected_block or not self.pages_service:
            return
        review = TextBlockService(self.pages_service.connection)
        review.update_review(self.selected_block, self.block_source.toPlainText(), self.block_order.value())
        current = HistoryService(self.pages_service.connection).snapshot("text_blocks", self.selected_block)
        x, y = self.geometry_inputs["x"].value(), self.geometry_inputs["y"].value()
        bbox = [x, y, x+self.geometry_inputs["width"].value(), y+self.geometry_inputs["height"].value()]
        if bbox != json.loads(current["bbox_json"]) or self.geometry_inputs["rotation"].value() != current["rotation"]:
            review.update_geometry(self.selected_block, bbox, self.geometry_inputs["rotation"].value())
        self._save_translation_debounced()
        edits = RenderEditService(self.pages_service.connection, self.project)
        self.apply_style(scope="block")
        if json.loads(current["erase_data_json"]).get("mode", "none") != self.erase_mode.currentText():
            edits.set_erase(self.selected_block, self.erase_mode.currentText())
        self.cache.clear()
        self.reload_pages(self.current_id)
        self.status_changed.emit(self.language.tr("review.saved"))

    def _schedule_translation_save(self) -> None:
        if not self._loading_block and self.selected_block and self.pages_service:
            self.translation_status.setText(self.language.tr("status.saving"))
            self.translation_timer.start()

    def _save_translation_debounced(self) -> None:
        self.translation_timer.stop()
        if not self.selected_block or not self.pages_service:
            return
        review = TextBlockService(self.pages_service.connection)
        existing = review.translation(self.selected_block)
        text = self.block_translation.toPlainText()
        notes = self.block_notes.toPlainText()
        if existing and existing["text"] == text and existing["notes"] == notes:
            self.translation_status.setText(self.language.tr("status.saved"))
            return
        if not existing and not text and not notes:
            return
        review.save_translation(self.selected_block, text, notes)
        self.translation_status.setText(self.language.tr("status.saved"))
        self.refresh_auto_fit()
        self.quality_warning_count = 0
        self.cache.clear()
        self._refresh_ocr_list()
        self.update_actions()

    def _style_changes(self) -> dict:
        return {"font": self.font_field.text().strip() or "Microsoft YaHei",
                "font_weight": self.font_weight_field.value(),
                "min_size": self.min_font_size_field.value(), "max_size": self.font_size_field.value(),
                "color": self.color_field.text().strip() or "#111111",
                "stroke": self.stroke_color_field.text().strip() or "#ffffff",
                "stroke_width": self.stroke_width_field.value(),
                "padding": self.padding_field.value(), "line_spacing": self.line_spacing_field.value(),
                "letter_spacing": self.letter_spacing_field.value(),
                "alignment": self.alignment_field.currentData(),
                "vertical_alignment": self.vertical_alignment_field.currentData(),
                "writing_mode": self.writing_mode_field.currentData(),
                "auto_fit": self.auto_fit_field.isChecked()}

    def apply_style(self, checked=False, scope: str | None = None) -> None:
        if not self.selected_block or not self.pages_service:
            return
        scope = scope or self.style_apply_to.currentData()
        service = ProjectStyleService(self.pages_service.connection)
        changes = self._style_changes()
        try:
            if scope == "project":
                service.update_preset(self.style_role.currentData(), changes)
            elif scope == "block":
                block = HistoryService(self.pages_service.connection).snapshot("text_blocks", self.selected_block)
                current = service.resolve(block)
                if any(current.get(key) != value for key, value in changes.items()):
                    service.set_override(self.selected_block, changes)
            else:
                page_ids = [self.current_id]
                if scope == "batch":
                    row = self.pages_service.connection.execute("SELECT batch_id FROM batch_pages WHERE page_id=?",
                                                               (self.current_id,)).fetchone()
                    if not row:
                        QMessageBox.information(self, self.language.tr("style.apply"), self.language.tr("dialog.no_batches"))
                        return
                    page_ids = BatchService(self.pages_service.connection).page_ids(row["batch_id"])
                service.apply_to_scope(self.selected_block, changes, page_ids)
            FontPreferences(self.config).used(changes["font"])
            selected = self.selected_block
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_block(selected)
            self.status_changed.emit(self.language.tr("style.applied"))
        except Exception as exc:
            QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def reset_style(self) -> None:
        if self.selected_block and self.pages_service:
            ProjectStyleService(self.pages_service.connection).reset_override(self.selected_block)
            selected = self.selected_block
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_block(selected)

    def _role_changed(self, *_args) -> None:
        if self._loading_block or not self.selected_block or not self.pages_service:
            return
        role = self.style_role.currentData()
        ProjectStyleService(self.pages_service.connection).set_role(self.selected_block, role)
        selected = self.selected_block
        self.cache.clear()
        self.reload_pages(self.current_id)
        self.select_block(selected)

    def refresh_auto_fit(self) -> None:
        if not self.selected_block:
            return
        try:
            fit = fit_layout(self.block_translation.toPlainText(), self._style_changes(),
                             self.geometry_inputs["width"].value(), self.geometry_inputs["height"].value())
            if self.model.simple_mode:
                self.fit_status_label.setText(self.language.tr("style.fit_simple_" + fit.status))
            else:
                self.fit_status_label.setText(self.language.tr("style.fit_result", status=self.language.tr("style.fit_" + fit.status),
                    size=fit.font.pointSize(), lines=len(fit.lines), height=round(fit.occupied_height*100)))
        except ValueError as exc:
            self.fit_status_label.setText(str(exc))

    def set_simple_mode(self, enabled: bool) -> None:
        self.model.simple_mode = enabled
        if self.model.pages:
            self.model.dataChanged.emit(self.model.index(0), self.model.index(len(self.model.pages)-1))
        if self.selected_block and self.pages_service:
            block = next((b for b in TextBlockService(self.pages_service.connection).for_page(self.current_id)
                          if b["id"] == self.selected_block), None)
            self.block_id_label.setText("" if enabled else block["text_uid"] if block else "")
        self.update_status()
        self.right_tabs.setTabVisible(5, not enabled)
        for form, widgets in ((self.style_form, (self.stroke_color_field, self.stroke_width_field,
                                                 self.font_weight_field)),
                              (self.typeset_form, (self.min_font_size_field, self.letter_spacing_field,
                                                   self.vertical_alignment_field, self.writing_mode_field))):
            for widget in widgets:
                form.setRowVisible(widget, not enabled)
        if self.selected_block:
            self.refresh_auto_fit()

    def show_project_styles(self) -> None:
        if not self.pages_service:
            return
        dialog = ProjectStylesDialog(ProjectStyleService(self.pages_service.connection), self.language,
                                     self.open_font_browser, self)
        dialog.changed.connect(self._project_styles_changed)
        dialog.exec()

    def _project_font_names(self) -> set[str]:
        if not self.pages_service:
            return set()
        names = {json.loads(row["settings_json"]).get("font", "") for row in
                 ProjectStyleService(self.pages_service.connection).list_presets()}
        for row in self.pages_service.connection.execute("SELECT style_override_json FROM text_blocks WHERE active=1"):
            names.add(json.loads(row[0] or "{}").get("font", ""))
        for row in self.pages_service.connection.execute("SELECT settings_json FROM styles"):
            names.add(json.loads(row[0] or "{}").get("font", ""))
        return {name for name in names if name}

    def _check_project_fonts(self) -> None:
        available = {family.casefold() for family in QFontDatabase.families()}
        self.missing_project_fonts = sorted(name for name in self._project_font_names()
                                            if name.casefold() not in available)
        if self.missing_project_fonts:
            self.status_changed.emit(self.language.tr("font.missing_found", fonts=", ".join(self.missing_project_fonts)))

    def replace_missing_fonts(self) -> None:
        if not self.pages_service:
            return
        self._check_project_fonts()
        if not self.missing_project_fonts:
            QMessageBox.information(self, self.language.tr("font.replace_missing"), self.language.tr("font.no_missing"))
            return
        old, accepted = QInputDialog.getItem(self, self.language.tr("font.replace_missing"),
                                            self.language.tr("font.missing_found", fonts=", ".join(self.missing_project_fonts)),
                                            self.missing_project_fonts, 0, False)
        if not accepted:
            return
        def chosen(new: str):
            scopes = [self.language.tr("font.replace_project")] + [self.language.tr("style.role_" + r) for r in ROLES]
            label, okay = QInputDialog.getItem(self, self.language.tr("font.replace_missing"),
                                               self.language.tr("font.replace_scope"), scopes, 0, False)
            if not okay:
                return
            role = None if label == scopes[0] else ROLES[scopes.index(label)-1]
            count = ProjectStyleService(self.pages_service.connection).replace_font(old, new, role)
            self._project_styles_changed()
            self._check_project_fonts()
            self.status_changed.emit(self.language.tr("font.replaced", count=count))
        self.open_font_browser("", self.language.tr("font.sample"), chosen)

    def _project_styles_changed(self) -> None:
        selected = self.selected_block
        self.cache.clear()
        self.reload_pages(self.current_id)
        if selected:
            self.select_block(selected)
        self.update_actions()

    def show_quality_check(self) -> None:
        self.run_quality_check(False)

    def run_quality_check(self, before_export: bool = False) -> None:
        if not self.project:
            return
        project = self.project
        def operation(progress, cancel):
            records = FontCatalog(config_dir() / "font_catalog.json").metadata()
            db = connect(project / "project.sqlite3")
            try:
                return QualityChecker(db, records).scan(progress, cancel)
            finally:
                db.close()
        def finished(report):
            if report.get("status") != "completed":
                return
            self.quality_warning_count = report["counts"]["error"] + report["counts"]["warning"]
            self.update_status()
            if before_export and report["counts"]["error"]:
                choice = QMessageBox.question(self, self.language.tr("quality.title"),
                    self.language.tr("quality.export_warning", count=report["counts"]["error"]),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if choice == QMessageBox.StandardButton.Yes:
                    self._show_quality_report(report)
                elif choice == QMessageBox.StandardButton.No:
                    self._start_export([page["id"] for page in self.model.pages])
            elif before_export:
                self._start_export([page["id"] for page in self.model.pages])
            else:
                self._show_quality_report(report)
        self.run_job(operation, finished, "status.quality_check")

    def _show_quality_report(self, report: dict) -> None:
        counts = report.get("counts", {})
        self.quality_summary.setText(self.language.tr("quality.summary", errors=counts.get("error", 0),
            warnings=counts.get("warning", 0), infos=counts.get("info", 0)))
        self.quality_list.clear()
        for issue in report["issues"]:
            page = next((i + 1 for i, row in enumerate(self.model.pages) if row["id"] == issue.get("page_id")), None)
            prefix = f"{page:03d}" if page else "—"
            if issue.get("text_uid"):
                if self.model.simple_mode:
                    number = issue.get("reading_order") or "?"
                    block = f" · {'文字框' if self.language.language == 'zh_CN' else 'Block'} {number}"
                else:
                    block = f" · {issue['text_uid']}"
            else:
                block = ""
            item = QListWidgetItem(f"{prefix}{block}  ·  {self.language.tr('quality.' + issue['code'])}")
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.quality_list.addItem(item)
        self.bottom_tabs.setCurrentIndex(3)
        self.bottom_tabs.show()

    def _locate_quality_issue(self, issue: dict) -> None:
        page_id = issue.get("page_id")
        for index, page in enumerate(self.model.pages):
            if page["id"] == page_id:
                self.left_tabs.setCurrentIndex(1 if issue.get("block_id") else 0)
                self.panel.setCurrentIndex(self.model.index(index))
                self.panel.scrollTo(self.model.index(index))
                if issue.get("block_id"):
                    self.select_block(issue["block_id"])
                return

    def erase_and_refill_current(self) -> None:
        if not self.selected_block or not self.pages_service:
            QMessageBox.information(self, self.language.tr("action.erase_refill"), self.language.tr("dialog.no_text_selected"))
            return
        text = self.block_translation.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, self.language.tr("action.erase_refill"), self.language.tr("dialog.translation_required"))
            self.right_tabs.setCurrentIndex(0)
            self.block_translation.setFocus()
            return
        try:
            WorkflowService(self.pages_service.connection, self.project).erase_and_refill(
                self.selected_block, text, self.erase_mode.currentText() if self.erase_mode.currentText() != "none" else "fill")
            selected = self.selected_block
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_block(selected)
            self.status_changed.emit(self.language.tr("status.erase_refill_done"))
        except Exception as exc:
            QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def erase_selected_block(self) -> None:
        if self.selected_block and self.pages_service:
            try:
                WorkflowService(self.pages_service.connection, self.project).erase_blocks([self.selected_block])
                selected = self.selected_block
                self.cache.clear()
                self.reload_pages(self.current_id)
                self.select_block(selected)
            except Exception as exc:
                QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def fill_selected_block(self) -> None:
        if not self.selected_block or not self.pages_service:
            return
        text = self.block_translation.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, self.language.tr("action.fill_only"), self.language.tr("dialog.translation_required"))
            return
        try:
            WorkflowService(self.pages_service.connection, self.project).fill_translation(self.selected_block, text)
            selected = self.selected_block
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_block(selected)
            self.status_changed.emit(self.language.tr("status.translation_saved"))
        except Exception as exc:
            QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def restore_selected_block(self) -> None:
        if not self.selected_block or not self.pages_service:
            return
        try:
            WorkflowService(self.pages_service.connection, self.project).restore_erase(self.selected_block)
            selected = self.selected_block
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_block(selected)
        except Exception as exc:
            QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def focus_translation_editor(self, block_id: str) -> None:
        self.select_block(block_id)
        self.right_tabs.setCurrentIndex(0)
        self.block_translation.setFocus()

    def _canvas_block_changed(self, block_id: str, bbox: list[float], rotation: float) -> None:
        if self.pages_service:
            TextBlockService(self.pages_service.connection).update_geometry(block_id, bbox, rotation)
            self.select_block(block_id)
            self.update_actions()

    def delete_block(self) -> None:
        if self.selected_block and self.pages_service:
            TextBlockService(self.pages_service.connection).delete(self.selected_block)
            self.cache.clear()
            self.reload_pages(self.current_id)

    def duplicate_block(self) -> None:
        if self.selected_block and self.pages_service:
            TextBlockService(self.pages_service.connection).duplicate(self.selected_block)
            self.reload_pages(self.current_id)

    def copy_style(self) -> None:
        self.copied_style = {"font": self.font_field.text(), "max_size": self.font_size_field.value(),
                             "color": self.color_field.text()}

    def paste_style(self) -> None:
        if self.selected_block and self.copied_style:
            RenderEditService(self.pages_service.connection, self.project).set_style(self.selected_block, self.copied_style)
            self.select_block(self.selected_block)

    def choose_font(self) -> None:
        self.open_font_browser(self.font_field.text(), self.block_translation.toPlainText(), self.font_field.setText)

    def open_font_browser(self, current: str, sample: str, callback) -> None:
        catalog = FontCatalog(config_dir() / "font_catalog.json")
        project_fonts = []
        if self.pages_service:
            project_fonts = [json.loads(row["settings_json"]).get("font", "") for row in
                             ProjectStyleService(self.pages_service.connection).list_presets()]
        page = dict(self.model.pages[self.current_row]) if 0 <= self.current_row < len(self.model.pages) else None
        block = (HistoryService(self.pages_service.connection).snapshot("text_blocks", self.selected_block)
                 if self.pages_service and self.selected_block else None)
        def operation(progress, cancel):
            records = catalog.metadata()
            suggestions = []
            if page and block:
                try:
                    image = (PdfRenderService(self.project).render(page, PREVIEW_DPI, "preview")
                             if page.get("source_kind") == "pdf" else ImageLoader().load(Path(page["path"]), 1200))
                    box = json.loads(block["bbox_json"])
                    sx, sy = image.width()/page["width"], image.height()/page["height"]
                    cropped = image.copy(int(box[0]*sx), int(box[1]*sy),
                                         max(1, int((box[2]-box[0])*sx)), max(1, int((box[3]-box[1])*sy)))
                    suggestions = recommend(cropped, records)
                except Exception:
                    pass
            return records, suggestions
        def show(result):
            records, suggestions = result
            dialog = FontPicker(records, current, self, config=self.config, language=self.language,
                                project_fonts=project_fonts, sample=sample, recommendations=suggestions)
            if self.selected_block:
                dialog.preview_changed.connect(lambda family: self.canvas.preview_font(
                    self.selected_block, family, self.block_translation.toPlainText()))
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            self.canvas.clear_font_preview()
            if accepted and dialog.selected():
                callback(dialog.selected())
                FontPreferences(self.config).used(dialog.selected())
                self.refresh_auto_fit()
        self.run_job(operation, show, "status.font_scan")

    def undo(self) -> None:
        command = HistoryService(self.pages_service.connection).next_command() if self.pages_service else None
        if self.pages_service and HistoryService(self.pages_service.connection).undo():
            self.cache.clear()
            self.reload_pages(self.current_id)
            if self.current_row >= 0:
                self.select_page(self.current_row)
            self.status_changed.emit(self.language.tr("status.undo_done", command=self._command_name(command)))

    def redo(self) -> None:
        command = HistoryService(self.pages_service.connection).next_command(True) if self.pages_service else None
        if self.pages_service and HistoryService(self.pages_service.connection).redo():
            self.cache.clear()
            self.reload_pages(self.current_id)
            if self.current_row >= 0:
                self.select_page(self.current_row)
            self.status_changed.emit(self.language.tr("status.redo_done", command=self._command_name(command)))

    def _command_name(self, command: str | None) -> str:
        return self.language.tr("history." + (command or "edit"))

    def edit_mask(self) -> None:
        if not self.selected_block or not self.project or self.current_row < 0:
            return
        page = self.model.pages[self.current_row]
        source = (PdfRenderService(self.project).render(page, PREVIEW_DPI, "preview")
                  if page.get("source_kind") == "pdf" else ImageLoader().load(Path(page["path"]), 1200))
        row = self.pages_service.connection.execute("SELECT mask_path FROM text_blocks WHERE id=?",
                                                    (self.selected_block,)).fetchone()
        from PySide6.QtGui import QImage
        mask = QImage(str(self.project / row["mask_path"])) if row and row["mask_path"] else None
        dialog = MaskDialog(source, mask, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            edits = RenderEditService(self.pages_service.connection, self.project)
            edits.set_mask(self.selected_block, dialog.view.mask)
            edits.set_erase(self.selected_block, "telea")
            self.cache.clear()
            self.reload_pages(self.current_id)

    def request_thumbnails(self) -> None:
        if not self.thumb_worker or not self.model.pages:
            return
        top = self.panel.indexAt(QPoint(2, 2)).row()
        top = max(0, top)
        count = self.panel.viewport().height() // 100 + 2
        indices = list(range(top, min(len(self.model.pages), top+count+5)))
        indices += list(range(max(0, top-5), top))
        pages = [self.model.pages[i] for i in indices if self.model.pages[i]["id"] not in self.model.pixmaps]
        self.thumbnail_generation += 1
        self.thumb_worker.request(self.thumbnail_generation, pages)

    def thumbnail_ready(self, generation: int, page_id: str, image, error: str) -> None:
        if generation != self.thumbnail_generation or not self.project:
            return
        self.model.thumbnail_ready(page_id, image, error)
        if error:
            self.pages_service.set_status(page_id, error)

    def navigate(self, delta: int) -> None:
        row = self.current_row + delta
        if 0 <= row < len(self.model.pages):
            self.panel.setCurrentIndex(self.model.index(row))
            self.panel.scrollTo(self.model.index(row))

    def go_to_page(self) -> None:
        if self.model.pages:
            number, accepted = QInputDialog.getInt(self, self.language.tr("dialog.go_to_page"), self.language.tr("dialog.display_page"), self.current_row+1, 1, len(self.model.pages))
            if accepted:
                self.panel.setCurrentIndex(self.model.index(number-1))
                self.panel.scrollTo(self.model.index(number-1))

    def move_page(self, delta: int) -> None:
        if self.current_id:
            self.pages_service.move(self.current_id, delta)
            self.reload_pages(self.current_id)

    def update_actions(self) -> None:
        for action in self.actions.values():
            action.setEnabled(self.project is not None)
        for key in ("images", "folder", "pdf", "ocr_page", "ocr_all", "ocr_resume", "batches", "project_styles", "replace_fonts", "quality_check", "word_export", "word_import", "export_page", "export_batch", "export_all", "export_resume", "relocate", "up", "down"):
            self.actions[key].setEnabled(self.project is not None and not self.jobs)
        self.actions["ocr_page"].setEnabled(self.current_id is not None and not self.jobs)
        self.actions["export_page"].setEnabled(self.current_id is not None and not self.jobs)
        self.actions["export_source"].setEnabled(bool(self.model.pages) and not self.jobs)
        self.actions["erase_quick"].setEnabled(self.current_id is not None and not self.jobs)
        self.actions["fill_translation"].setEnabled(self.current_id is not None and not self.jobs)
        self.actions["erase_refill"].setEnabled(self.selected_block is not None and not self.jobs)
        for key in ("copy_style", "paste_style", "duplicate_block", "delete_block"):
            self.actions[key].setEnabled(self.selected_block is not None and not self.jobs)
        self.actions["paste_style"].setEnabled(self.selected_block is not None and self.copied_style is not None and not self.jobs)
        self.actions["previous"].setEnabled(self.current_row > 0)
        self.actions["next"].setEnabled(0 <= self.current_row < len(self.model.pages)-1)
        self.actions["up"].setEnabled(self.current_row > 0 and not self.jobs)
        self.actions["down"].setEnabled(0 <= self.current_row < len(self.model.pages)-1 and not self.jobs)
        history = HistoryService(self.pages_service.connection) if self.pages_service else None
        for key, redo in (("undo", False), ("redo", True)):
            command = history.next_command(redo) if history else None
            self.actions[key].setEnabled(command is not None and not self.jobs)
            label = self.language.tr("action." + key)
            if command:
                label += " " + self._command_name(command)
            self.actions[key].setText(label)
            self.actions[key].setToolTip(label)

    def update_status(self) -> None:
        if not 0 <= self.current_row < len(self.model.pages):
            return
        p = self.model.pages[self.current_row]
        zoom = self.canvas.transform().m11() * 100
        tr = self.language.tr
        count = p.get("text_count", 0)
        translated = p.get("translated_count", 0)
        erased = p.get("erased_count", 0)
        next_key = ("status.next_ocr" if not count else "status.next_translate" if not translated
                    else "status.next_refill" if erased < translated else "status.next_export")
        self.status_changed.emit(tr("status.page_compact", page=self.current_row+1, total=len(self.model.pages),
                                    uid="" if self.model.simple_mode else p["page_uid"], zoom=f"{zoom:.0f}", ocr=count,
                                    translated=translated, erased=p.get("typeset_count", 0)) +
                                 ("  ⚠ " + str(self.quality_warning_count) if self.quality_warning_count else "") +
                                 "   " + tr(next_key))
        mode = tr("source.copy" if p["stored_path"] else "source.reference")
        self.inspector.setText(tr("page.inspector", uid="" if self.model.simple_mode else p["page_uid"], order=p["display_order"],
                                  label=self.language.display_label(p), filename=p["filename"],
                                  width=p["width"], height=p["height"], mode=mode,
                                  status=tr(f"status.{p['status']}")))

    def run_job(self, operation, callback, title: str) -> None:
        job = Job(operation, self)
        self.jobs.append(job)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.progress_label.show()
        self._job_title = title
        self._last_progress = None
        self.progress_label.setText(self.language.tr(title))
        self.bottom_tabs.setCurrentIndex(0)
        self.bottom_tabs.show()
        self.busy_changed.emit(True)
        self.update_actions()
        job.progress.connect(self.on_progress)
        job.result.connect(callback)
        job.error.connect(lambda text: QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), self.language.user_error(text)))
        job.finished.connect(lambda: self.finish_job(job))
        job.start()

    def on_progress(self, value: int, total: int, text: str) -> None:
        self._last_progress = (value, total, text)
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(value)
        task = self.language.progress_text(text)
        self.progress_label.setText(self.language.tr("status.job_progress", task=task, value=value, total=total))

    def finish_job(self, job: Job) -> None:
        if job in self.jobs:
            self.jobs.remove(job)
        job.deleteLater()
        if not self.jobs:
            self.progress.hide()
            self.progress_label.clear()
            self.progress_label.hide()
            self._job_title = ""
            self._last_progress = None
            bottom_action = getattr(self.window(), "bottom_action", None)
            if self.bottom_tabs.currentIndex() == 0 and not (bottom_action and bottom_action.isChecked()):
                self.bottom_tabs.hide()
        self.busy_changed.emit(bool(self.jobs))
        self.update_actions()
        if not self.jobs and self._drop_queue:
            QTimer.singleShot(0, self._next_drop_import)

    def import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, self.language.tr("dialog.import_images"), "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.JPG *.JPEG *.PNG *.WEBP *.BMP)")
        if files:
            self.start_scan([Path(p) for p in files])

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.language.tr("dialog.import_folder"))
        if folder:
            self.start_scan(Path(folder))

    def import_pdf(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.language.tr("action.import_pdf"), "", "PDF (*.pdf *.PDF)")
        if filename:
            self.import_pdf_path(Path(filename))

    def import_pdf_path(self, source: Path) -> None:
        if not self.project:
            return
        project = self.project
        self.run_job(lambda progress, cancel: PdfImporter(project).import_file(source, progress, cancel),
                     self.import_finished, "status.importing")

    def import_paths(self, paths: list[Path]) -> None:
        images: list[Path] = []
        queue: list[Path | list[Path]] = []
        for path in paths:
            if path.is_dir():
                queue.append(path)
            elif path.suffix.lower() == ".pdf":
                queue.append(path)
            elif path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                images.append(path)
        if images:
            queue.append(images)
        self._drop_queue.extend(queue)
        if not self.jobs:
            self._next_drop_import()

    def _next_drop_import(self) -> None:
        if self.jobs or not self._drop_queue or not self.project:
            return
        item = self._drop_queue.pop(0)
        if isinstance(item, list) or item.is_dir():
            self.start_scan(item)
        else:
            self.import_pdf_path(item)

    def export_source_dialog(self) -> None:
        if not self.pages_service:
            return
        choices = [self.language.tr(key) for key in ("scope.page", "scope.batch", "scope.project")]
        scope, accepted = QInputDialog.getItem(self, self.language.tr("action.export_source"),
                                               self.language.tr("dialog.export_scope"), choices, 0, False)
        if not accepted:
            return
        if scope == choices[0]:
            ids = [self.current_id] if self.current_id else []
        elif scope == choices[1]:
            batches = BatchService(self.pages_service.connection).list_batches()
            if not batches:
                QMessageBox.information(self, self.language.tr("action.export_source"), self.language.tr("dialog.no_batches"))
                return
            labels = [f"Batch {b['batch_number']}" for b in batches]
            chosen, ok = QInputDialog.getItem(self, self.language.tr("action.export_source"),
                                              self.language.tr("dialog.choose_batch"), labels, 0, False)
            if not ok:
                return
            ids = BatchService(self.pages_service.connection).page_ids(batches[labels.index(chosen)]["id"])
        else:
            ids = [page["id"] for page in self.model.pages]
        filename, selected_filter = QFileDialog.getSaveFileName(self, self.language.tr("action.export_source"),
                                                  str(self.project / "documents" / "original-text.docx"),
                                                  "Word (*.docx);;TSV (*.tsv)")
        if filename:
            try:
                workflow = WorkflowService(self.pages_service.connection, self.project)
                destination = Path(filename)
                if "TSV" in selected_filter:
                    destination = destination.with_suffix(".tsv")
                    count = workflow.export_source(ids, destination)
                else:
                    destination = destination.with_suffix(".docx")
                    count = workflow.export_source_docx(ids, destination)
                self.export_label.setText(f"{count} text blocks → {destination}")
                self.bottom_tabs.setCurrentIndex(2)
                self.bottom_tabs.show()
            except Exception as exc:
                QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def erase_quick_dialog(self) -> None:
        if not self.pages_service or not self.current_id:
            return
        choices = [self.language.tr(key) for key in ("scope.block", "scope.selected_blocks", "scope.page_blocks")]
        scope, accepted = QInputDialog.getItem(self, self.language.tr("action.erase_quick"),
                                               self.language.tr("dialog.erase_scope"), choices, 0, False)
        if not accepted:
            return
        if scope == choices[0]:
            ids = [self.selected_block] if self.selected_block else []
        elif scope == choices[1]:
            ids = [item.data(Qt.ItemDataRole.UserRole) for item in self.ocr_list.selectedItems()]
        else:
            ids = [block["id"] for block in TextBlockService(self.pages_service.connection).for_page(self.current_id)]
        if not ids:
            QMessageBox.information(self, self.language.tr("action.erase_quick"), self.language.tr("dialog.no_text_selected"))
            return
        try:
            WorkflowService(self.pages_service.connection, self.project).erase_blocks(ids)
            self.cache.clear()
            self.reload_pages(self.current_id)
            self.select_page(self.current_row)
        except Exception as exc:
            QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def enable_text_tool(self) -> None:
        self.canvas.text_tool = self.actions["fill_translation"].isChecked()
        self.canvas.setCursor(Qt.CursorShape.IBeamCursor if self.canvas.text_tool else Qt.CursorShape.ArrowCursor)
        self.left_tabs.setCurrentIndex(1)
        self.right_tabs.setCurrentIndex(0)
        if self.canvas.text_tool:
            self.status_changed.emit(self.language.tr("status.text_tool"))

    def edit_translation_on_canvas(self, block_id: str) -> None:
        if not self.pages_service:
            return
        review = TextBlockService(self.pages_service.connection)
        previous = review.translation(block_id)
        text, accepted = QInputDialog.getMultiLineText(self, self.language.tr("action.fill_translation"),
                                                       self.language.tr("review.translation"),
                                                       previous["text"] if previous else "")
        if accepted:
            try:
                WorkflowService(self.pages_service.connection, self.project).fill_translation(block_id, text)
                self.cache.clear()
                self.reload_pages(self.current_id)
                self.select_page(self.current_row)
                self.select_block(block_id)
            except Exception as exc:
                QMessageBox.warning(self, self.language.tr("dialog.operation_failed"), str(exc))

    def show_models(self) -> None:
        status = ModelManager().status()
        QMessageBox.information(self, self.language.tr("action.models"),
                                self.language.tr("dialog.model_status", installed=status["installed"],
                                                 model=status["model"], path=status["path"],
                                                 missing=", ".join(status["missing"]) or "—"))

    def ocr_current_page(self) -> None:
        if self.current_id:
            self._start_ocr([self.current_id])

    def ocr_all_pages(self) -> None:
        self._start_ocr([page["id"] for page in self.model.pages])

    def resume_ocr(self) -> None:
        if not self.pages_service:
            return
        row = self.pages_service.connection.execute("""SELECT id FROM tasks WHERE kind='ocr'
            AND status IN ('paused','interrupted','failed','pending') ORDER BY created_at LIMIT 1""").fetchone()
        if row:
            self._start_ocr(task_id=row["id"])
        else:
            QMessageBox.information(self, self.language.tr("action.ocr_resume"), self.language.tr("dialog.no_ocr_task"))

    def _start_ocr(self, page_ids: list[str] | None = None, task_id: str | None = None) -> None:
        if not page_ids and task_id is None:
            return
        model = ModelManager().status()
        if not model["installed"]:
            self.show_models()
            return
        project = self.project
        self.run_job(lambda progress, cancel: run_ocr_task(project, page_ids, task_id, progress, cancel),
                     self._ocr_finished, "status.ocr")

    def _ocr_finished(self, result: dict) -> None:
        if self.current_row >= 0:
            self.select_page(self.current_row)
        self.status_changed.emit(self.language.tr("status.ocr_finished", done=result["completed"],
                                                 total=result["total"], status=result["status"]))

    def create_batches(self) -> None:
        if not self.pages_service:
            return
        size, accepted = QInputDialog.getInt(self, self.language.tr("action.create_batches"),
                                             self.language.tr("dialog.batch_size"), 100, 1, 1000)
        if accepted:
            count = len(BatchService(self.pages_service.connection).create_for_unassigned(size))
            self._refresh_side_panels()
            QMessageBox.information(self, self.language.tr("action.create_batches"),
                                    self.language.tr("dialog.batches_created", count=count))

    def export_word(self) -> None:
        if not self.pages_service:
            return
        batches = BatchService(self.pages_service.connection).list_batches()
        if not batches:
            QMessageBox.information(self, self.language.tr("action.word_export"), self.language.tr("dialog.no_batches"))
            return
        labels = [f"Batch {b['batch_number']} ({b['page_count']})" for b in batches]
        selected, accepted = QInputDialog.getItem(self, self.language.tr("action.word_export"),
                                                   self.language.tr("dialog.choose_batch"), labels, 0, False)
        if not accepted:
            return
        mode, accepted = QInputDialog.getItem(self, self.language.tr("action.word_export"),
                                              self.language.tr("dialog.word_mode"), ["light", "standard", "full"], 0, False)
        if not accepted:
            return
        batch_id = batches[labels.index(selected)]["id"]
        project = self.project
        def operation(progress, cancel):
            db = connect(project / "project.sqlite3")
            try:
                return WordExchange(db, project).export(batch_id, mode)
            finally:
                db.close()
        self.run_job(operation, lambda path: QMessageBox.information(self, self.language.tr("action.word_export"),
                              self.language.tr("dialog.word_exported", path=str(path))), "status.word_export")

    def import_word(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, self.language.tr("action.word_import"), "", "Word (*.docx)")
        if not filename or not self.project:
            return
        project = self.project
        def operation(progress, cancel):
            db = connect(project / "project.sqlite3")
            try:
                return WordExchange(db, project).import_document(Path(filename))
            finally:
                db.close()
        self.run_job(operation, lambda report: QMessageBox.information(self, self.language.tr("action.word_import"),
                              self.language.tr("dialog.word_imported", **report)), "status.word_import")

    def _start_export(self, ids: list[str] | None = None, task_id: str | None = None) -> None:
        fmt, accepted = QInputDialog.getItem(self, self.language.tr("action.export_all"),
                                             self.language.tr("dialog.export_format"), ["png", "jpg", "webp"], 0, False)
        if not accepted:
            return
        project = self.project
        def finished(result):
            message = self.language.tr("dialog.export_finished", status=result["status"],
                                       done=result["completed"], total=result["total"], path=result["output"])
            self.export_label.setText(message)
            self.bottom_tabs.setCurrentIndex(2)
            QMessageBox.information(self, self.language.tr("action.export_all"), message)
        self.run_job(lambda progress, cancel: export_pages(project, ids, fmt, task_id, progress, cancel),
                     finished, "status.exporting")

    def export_current_page(self) -> None:
        if self.current_id:
            self._start_export([self.current_id])

    def export_all_pages(self) -> None:
        if self.model.pages:
            self.run_quality_check(True)

    def export_current_batch(self) -> None:
        if not self.pages_service:
            return
        batches = BatchService(self.pages_service.connection).list_batches()
        if not batches:
            QMessageBox.information(self, self.language.tr("action.export_batch"), self.language.tr("dialog.no_batches"))
            return
        labels = [f"Batch {batch['batch_number']} ({batch['page_count']})" for batch in batches]
        selected, accepted = QInputDialog.getItem(self, self.language.tr("action.export_batch"),
                                                   self.language.tr("dialog.choose_batch"), labels, 0, False)
        if accepted:
            self._start_export(BatchService(self.pages_service.connection).page_ids(batches[labels.index(selected)]["id"]))

    def resume_export(self) -> None:
        if not self.pages_service:
            return
        row = self.pages_service.connection.execute("""SELECT id FROM tasks WHERE kind='final_export'
            AND status IN ('paused','interrupted','failed','pending') ORDER BY created_at LIMIT 1""").fetchone()
        if row:
            self._start_export(task_id=row["id"])
        else:
            QMessageBox.information(self, self.language.tr("action.export_resume"), self.language.tr("dialog.no_export_task"))

    def start_scan(self, source: Path | list[Path]) -> None:
        project = self.project
        def operation(progress, cancel):
            scan = scan_folder(source) if isinstance(source, Path) else scan_files(source)
            return ImageImporter(project).validate(scan, progress, cancel)
        self.run_job(operation, self.confirm_import, "status.scanning")

    def confirm_import(self, preview: ImportPreview) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.language.tr("dialog.import_preview"))
        dialog.setText(self.language.tr("dialog.import_summary", found=len(preview.candidates), ignored=preview.ignored,
                                         broken=len(preview.errors), duplicates=preview.duplicates))
        if preview.errors:
            dialog.setDetailedText("\n".join(preview.errors))
        skip = dialog.addButton(self.language.tr("dialog.skip_duplicates"), QMessageBox.ButtonRole.AcceptRole)
        anyway = dialog.addButton(self.language.tr("dialog.import_anyway"), QMessageBox.ButtonRole.ActionRole) if preview.duplicates else None
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        cancel.setText(self.language.tr("dialog.cancel"))
        dialog.setDefaultButton(skip)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked != skip and (anyway is None or clicked != anyway):
            return
        importer = ImageImporter(self.project)
        self.run_job(lambda progress, cancel: importer.commit(preview, clicked == anyway, progress, cancel),
                     self.import_finished, "status.importing")

    def import_finished(self, count: int) -> None:
        self.reload_pages()
        self.status_changed.emit(self.language.tr("status.imported", count=count, total=len(self.model.pages)))

    def relocate(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.language.tr("dialog.relocate_source"))
        if not folder:
            return
        project = self.project
        def operation(progress, cancel):
            db = connect(project / "project.sqlite3")
            try:
                return PageService(db, project).relocate(Path(folder), progress)
            finally:
                db.close()
        def finished(report):
            self.cache.clear()
            self.thumbnail_cache.clear()
            self.reload_pages()
            QMessageBox.information(self, self.language.tr("action.relocate"),
                                    self.language.tr("dialog.relocate_result", relocated=report["relocated"], unresolved=len(report["unresolved"])))
        self.run_job(operation, finished, "status.relocating")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.thumbnail_timer.start()
