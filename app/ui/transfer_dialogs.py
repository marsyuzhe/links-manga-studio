"""Present existing import and image-export options; persistence stays in services."""
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QPlainTextEdit)
from .components import CollapsibleSection, dialog_layout, localize_buttons


class ImportPreviewDialog(QDialog):
    def __init__(self, preview, language, parent=None):
        super().__init__(parent)
        tr = language.tr
        self.include_duplicates = False
        self.setWindowTitle(tr("dialog.import_preview"))
        self.resize(560, 300)
        layout = dialog_layout(self)
        summary = QLabel(tr("dialog.import_summary", found=len(preview.candidates),
            ignored=preview.ignored, broken=len(preview.errors), duplicates=preview.duplicates))
        summary.setWordWrap(True)
        layout.addWidget(summary)
        if preview.errors:
            detail = QPlainTextEdit("\n".join(preview.errors))
            detail.setReadOnly(True)
            detail.setMaximumHeight(130)
            layout.addWidget(CollapsibleSection(tr("ui.advanced_options"), detail))
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(buttons, tr)
        self.import_button = buttons.addButton(tr("dialog.skip_duplicates"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_button.setProperty("variant", "primary")
        self.import_button.setEnabled(bool(preview.candidates))
        self.import_button.setDefault(True)
        if preview.duplicates:
            include = buttons.addButton(tr("dialog.import_anyway"), QDialogButtonBox.ButtonRole.ActionRole)
            include.setProperty("variant", "ghost")
            include.clicked.connect(self.include_and_accept)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def include_and_accept(self):
        self.include_duplicates = True
        self.accept()


class ExportOptionsDialog(QDialog):
    def __init__(self, project, page_count, language, parent=None):
        super().__init__(parent)
        tr = language.tr
        self.setWindowTitle(tr("ui.export_options"))
        self.resize(520, 300)
        layout = dialog_layout(self)
        form = QFormLayout()
        self.format = QComboBox()
        self.format.addItems(["png", "jpg", "webp"])
        form.addRow(tr("dialog.export_format"), self.format)
        form.addRow(tr("dialog.export_scope"), QLabel(tr("ui.export_pages", count=page_count)))
        self.destination = QLineEdit(str(project / "exports"))
        self.destination.setReadOnly(True)
        form.addRow(tr("ui.destination"), self.destination)
        self.quality = QLabel()
        form.addRow(tr("ui.image_quality"), self.quality)
        def update_quality():
            self.quality.setText(tr("ui.lossless") if self.format.currentText()=="png" else "90%")
        self.format.currentIndexChanged.connect(update_quality)
        update_quality()
        layout.addLayout(form)
        hint = QLabel(tr("ui.export_subfolder"))
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        localize_buttons(buttons, tr)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("menu.export"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
