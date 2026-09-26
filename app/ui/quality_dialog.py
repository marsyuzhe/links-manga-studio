"""Navigable quality-check results."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout


class QualityDialog(QDialog):
    locate = Signal(object)

    def __init__(self, report: dict, language, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(language.tr("quality.title"))
        self.resize(660, 520)
        layout = QVBoxLayout(self)
        counts = report.get("counts", {})
        summary = QLabel(language.tr("quality.summary", errors=counts.get("error", 0),
                                    warnings=counts.get("warning", 0), infos=counts.get("info", 0)))
        layout.addWidget(summary)
        self.list = QListWidget()
        for issue in report["issues"]:
            prefix = issue.get("text_uid") or issue.get("page_uid") or "—"
            item = QListWidgetItem(f"{prefix} · {language.tr('quality.' + issue['code'])}")
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.list.addItem(item)
        layout.addWidget(self.list)
        self.list.itemDoubleClicked.connect(self._locate)
        button = QPushButton(language.tr("quality.locate"))
        button.clicked.connect(lambda: self._locate(self.list.currentItem()))
        layout.addWidget(button)

    def _locate(self, item) -> None:
        if item:
            self.locate.emit(item.data(Qt.ItemDataRole.UserRole))
            self.accept()
