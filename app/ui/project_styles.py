"""Project-wide style presets with a live sample and undoable apply."""
from __future__ import annotations

import json
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                              QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout)

from app.styles.project_styles import ProjectStyleService, ROLES


class ProjectStylesDialog(QDialog):
    changed = Signal()

    def __init__(self, service: ProjectStyleService, language, browse_font, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.tr_text = language.tr
        self.browse_font = browse_font
        self.setWindowTitle(self.tr_text("style.project_title"))
        self.resize(520, 430)
        layout = QVBoxLayout(self)
        self.role = QComboBox()
        for role in ROLES:
            self.role.addItem(self.tr_text("style.role_" + role), role)
        layout.addWidget(self.role)
        self.sample = QLabel(self.tr_text("style.sample"))
        self.sample.setMinimumHeight(110)
        self.sample.setStyleSheet("background:#f9f8f4; color:#111; border-radius:10px; padding:14px")
        layout.addWidget(self.sample)
        form = QFormLayout()
        self.font = QLineEdit()
        font_row = QHBoxLayout()
        font_row.addWidget(self.font)
        browse = QPushButton(self.tr_text("font.browser"))
        browse.clicked.connect(lambda: self.browse_font(self.font.text(), self.sample.text(), self._font_chosen))
        font_row.addWidget(browse)
        form.addRow(self.tr_text("review.font"), font_row)
        self.min_size = QSpinBox()
        self.min_size.setRange(6, 300)
        self.max_size = QSpinBox()
        self.max_size.setRange(6, 300)
        self.padding = QSpinBox()
        self.padding.setRange(0, 200)
        self.color = QLineEdit()
        self.alignment = QComboBox()
        for key in ("left", "center", "right"):
            self.alignment.addItem(self.tr_text("style.align_" + key), key)
        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(.5, 3)
        self.line_spacing.setSingleStep(.05)
        form.addRow(self.tr_text("style.min_size"), self.min_size)
        form.addRow(self.tr_text("style.max_size"), self.max_size)
        form.addRow(self.tr_text("style.padding"), self.padding)
        form.addRow(self.tr_text("review.color"), self.color)
        form.addRow(self.tr_text("style.alignment"), self.alignment)
        form.addRow(self.tr_text("style.line_spacing"), self.line_spacing)
        layout.addLayout(form)
        self.apply_button = QPushButton(self.tr_text("style.apply_project"))
        self.apply_button.clicked.connect(self.apply)
        layout.addWidget(self.apply_button)
        self.feedback = QLabel()
        layout.addWidget(self.feedback)
        self.role.currentIndexChanged.connect(self.load_role)
        for control in (self.font, self.color):
            control.textChanged.connect(self.update_sample)
        for control in (self.min_size, self.max_size, self.padding, self.line_spacing):
            control.valueChanged.connect(self.update_sample)
        self.load_role()

    def _font_chosen(self, family: str) -> None:
        self.font.setText(family)

    def load_role(self, *_args) -> None:
        settings = json.loads(self.service.preset(self.role.currentData())["settings_json"])
        self.font.setText(settings.get("font", "Microsoft YaHei"))
        self.min_size.setValue(int(settings.get("min_size", 18)))
        self.max_size.setValue(int(settings.get("max_size", 72)))
        self.padding.setValue(int(settings.get("padding", 8)))
        self.color.setText(settings.get("color", "#111111"))
        self.alignment.setCurrentIndex(max(0, self.alignment.findData(settings.get("alignment", "center"))))
        self.line_spacing.setValue(float(settings.get("line_spacing", 1)))
        self.feedback.clear()
        self.update_sample()

    def update_sample(self, *_args) -> None:
        self.sample.setFont(QFont(self.font.text() or "Microsoft YaHei", min(self.max_size.value(), 28)))

    def apply(self) -> None:
        changes = {"font": self.font.text().strip() or "Microsoft YaHei", "min_size": self.min_size.value(),
                   "max_size": self.max_size.value(), "padding": self.padding.value(),
                   "color": self.color.text().strip() or "#111111", "alignment": self.alignment.currentData(),
                   "line_spacing": self.line_spacing.value()}
        try:
            self.service.update_preset(self.role.currentData(), changes)
        except ValueError as exc:
            self.feedback.setText(str(exc))
            return
        self.feedback.setText(self.tr_text("style.applied"))
        self.changed.emit()
