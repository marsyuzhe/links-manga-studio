"""Task-oriented settings navigator for existing local preferences and tools."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                              QListWidget, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from .components import SectionHeader


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.host = window
        zh = window.language.language == "zh_CN"
        self.setWindowTitle("设置" if zh else "Settings")
        self.resize(780, 520)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(16)
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(160)
        self.pages = QStackedWidget()
        outer.addWidget(self.navigation)
        outer.addWidget(self.pages, 1)
        self.sections = (("常规", "General"), ("外观", "Appearance"), ("OCR", "OCR"),
                    ("翻译", "Translation"), ("排版", "Typesetting"),
                    ("导出", "Export"), ("高级", "Advanced"), ("关于", "About"))
        self.section_headers = []
        for cn, en in self.sections:
            title = cn if zh else en
            self.navigation.addItem(title)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)
            header = SectionHeader(title)
            self.section_headers.append(header)
            layout.addWidget(header)
            layout.addStretch(1)
            self.pages.addWidget(page)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)

        general = self.pages.widget(0).layout()
        self.simple = QCheckBox("简洁模式" if zh else "Simple mode")
        self.simple.setChecked(window.simple_action.isChecked())
        self.simple.toggled.connect(window.simple_action.setChecked)
        general.insertWidget(1, self.simple)
        cache_row = QWidget()
        cache_layout = QFormLayout(cache_row)
        self.cache_size = QSpinBox()
        self.cache_size.setRange(16, 2048)
        self.cache_size.setSuffix(" MB")
        self.cache_size.setValue(window.service.config.image_cache_mb)
        self.cache_size.valueChanged.connect(self._set_cache_size)
        cache_layout.addRow("图片缓存上限" if zh else "Image cache limit", self.cache_size)
        general.insertWidget(2, cache_row)

        appearance = self.pages.widget(1).layout()
        theme_row = QWidget()
        theme_form = QFormLayout(theme_row)
        self.theme_choice = QComboBox()
        for code, cn, en in (("dark", "深色", "Dark"), ("light", "浅色", "Light"),
                             ("system", "跟随系统", "System")):
            self.theme_choice.addItem(cn if zh else en, code)
        self.theme_choice.setCurrentIndex(self.theme_choice.findData(window.theme.mode))
        self.theme_choice.currentIndexChanged.connect(lambda: window.set_theme(self.theme_choice.currentData()))
        theme_form.addRow("主题" if zh else "Theme", self.theme_choice)
        self.language_choice = QComboBox()
        self.language_choice.addItem("简体中文", "zh_CN")
        self.language_choice.addItem("English", "en_US")
        self.language_choice.setCurrentIndex(self.language_choice.findData(window.language.language))
        self.language_choice.currentIndexChanged.connect(lambda: window.language.set_language(self.language_choice.currentData()))
        theme_form.addRow("语言" if zh else "Language", self.language_choice)
        appearance.insertWidget(1, theme_row)

        ocr = self.pages.widget(2).layout()
        self.ocr_button = self._button(ocr, "查看本地 OCR 模型" if zh else "View local OCR models", window.workspace.show_models)
        translation = self.pages.widget(3).layout()
        self.translation_hint = QLabel("译文会在输入停顿后自动保存。" if zh else
                                       "Translations save automatically after typing pauses.")
        translation.insertWidget(1, self.translation_hint)
        typesetting = self.pages.widget(4).layout()
        self.styles_button = self._button(typesetting, "项目文字样式" if zh else "Project text styles", window.workspace.show_project_styles)
        export = self.pages.widget(5).layout()
        self.export_hint = QLabel("图片导出目录位于当前项目的 exports 文件夹。" if zh else
                                  "Images are exported into the current project's exports folder.")
        export.insertWidget(1, self.export_hint)
        advanced = self.pages.widget(6).layout()
        self.diagnostics_button = self._button(advanced, "环境诊断" if zh else "Diagnostics", window.show_diagnostics)
        self.logs_button = self._button(advanced, "打开日志文件夹" if zh else "Open log folder", window.open_log_action.trigger)
        about = self.pages.widget(7).layout()
        from app.branding import DISPLAY_NAME, AUTHOR_EN
        about.insertWidget(1, QLabel(f"{DISPLAY_NAME} · {AUTHOR_EN}"))
        self.about_button = self._button(about, "查看关于" if zh else "Open About", window.show_about)
        window.language.changed.connect(self.retranslate)

    def retranslate(self, *_args) -> None:
        zh = self.host.language.language == "zh_CN"
        self.setWindowTitle("设置" if zh else "Settings")
        for index, ((cn, en), header) in enumerate(zip(self.sections, self.section_headers)):
            title = cn if zh else en
            self.navigation.item(index).setText(title)
            header.setText(title)
        self.simple.setText("简洁模式" if zh else "Simple mode")
        self.theme_choice.setItemText(0, "深色" if zh else "Dark")
        self.theme_choice.setItemText(1, "浅色" if zh else "Light")
        self.theme_choice.setItemText(2, "跟随系统" if zh else "System")
        theme_form = self.theme_choice.parentWidget().layout()
        theme_form.labelForField(self.theme_choice).setText("主题" if zh else "Theme")
        theme_form.labelForField(self.language_choice).setText("语言" if zh else "Language")
        cache_form = self.cache_size.parentWidget().layout()
        cache_form.labelForField(self.cache_size).setText("图片缓存上限" if zh else "Image cache limit")
        self.ocr_button.setText("查看本地 OCR 模型" if zh else "View local OCR models")
        self.translation_hint.setText("译文会在输入停顿后自动保存。" if zh else "Translations save automatically after typing pauses.")
        self.styles_button.setText("项目文字样式" if zh else "Project text styles")
        self.export_hint.setText("图片导出目录位于当前项目的 exports 文件夹。" if zh else
                                 "Images are exported into the current project's exports folder.")
        self.diagnostics_button.setText("环境诊断" if zh else "Diagnostics")
        self.logs_button.setText("打开日志文件夹" if zh else "Open log folder")
        self.about_button.setText("查看关于" if zh else "Open About")

    def _button(self, layout, text, handler):
        button = QPushButton(text)
        button.clicked.connect(handler)
        layout.insertWidget(layout.count()-1, button)
        return button

    def _set_cache_size(self, value: int) -> None:
        self.host.service.config.data["image_cache_mb"] = value
        self.host.service.config.save()
        self.host.workspace.cache.limit_bytes = value * 1024 * 1024
        if self.host.workspace.cache.used_bytes > self.host.workspace.cache.limit_bytes:
            self.host.workspace.cache.clear()
