"""Small reusable presentation components without business logic."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


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


class EmptyState(QWidget):
    def __init__(self, title="", hint="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = SectionHeader(title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel(hint)
        self.hint.setProperty("role", "muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
