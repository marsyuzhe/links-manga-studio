"""Small reusable presentation components without business logic."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget, QDialogButtonBox


def localize_buttons(box, tr):
    for standard, key in ((QDialogButtonBox.StandardButton.Save, "ui.save"),
            (QDialogButtonBox.StandardButton.Cancel, "dialog.cancel"),
            (QDialogButtonBox.StandardButton.Close, "ui.close"),
            (QDialogButtonBox.StandardButton.Ok, "dialog.confirm"),
            (QDialogButtonBox.StandardButton.Yes, "ui.yes"),
            (QDialogButtonBox.StandardButton.No, "ui.no")):
        button = box.button(standard)
        if button:
            button.setText(tr(key))
            primary = standard in (QDialogButtonBox.StandardButton.Save, QDialogButtonBox.StandardButton.Ok)
            button.setProperty("variant", "primary" if primary else "ghost")
    box.setCenterButtons(False)


class CollapsibleSection(QWidget):
    """A flat disclosure row; expanded content is never another card."""
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.header = QToolButton()
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.header)
        layout.addWidget(content)
        content.hide()
        self.header.toggled.connect(content.setVisible)
        self.header.toggled.connect(lambda opened: self.header.setArrowType(
            Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow))


class ActionButton(QPushButton):
    def __init__(self, text="", *, variant="ghost", icon=None, parent=None):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        if icon is not None:
            self.setIcon(icon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SectionHeader(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setProperty("role", "section")


def dialog_layout(dialog):
    """Standard dialog safe inset in logical pixels."""
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)
    return layout


def exec_dialog(dialog):
    """Dispose a one-shot modal after returning control to its caller."""
    try:
        return dialog.exec()
    finally:
        dialog.deleteLater()


def polish_standard_prompt(dialog):
    """Apply product inset/footer to Qt message/input prompts, not native file pickers."""
    if dialog.layout():
        dialog.layout().setContentsMargins(16, 16, 16, 16)
    owner = dialog.parentWidget()
    while owner is not None:
        language = getattr(owner, "language", None)
        if language:
            for box in dialog.findChildren(QDialogButtonBox):
                localize_buttons(box, language.tr)
            break
        owner = owner.parentWidget()
    dialog.adjustSize()
