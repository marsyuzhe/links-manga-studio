"""Searchable Windows font browser with non-persistent preview and user collections."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                              QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

from app.rendering.fonts import FontPreferences


class FontPicker(QDialog):
    preview_changed = Signal(str)

    def __init__(self, fonts: list[dict] | list[str], current: str, parent=None, *,
                 config=None, language=None, project_fonts: list[str] | None = None,
                 sample: str = "", recommendations: list[dict] | None = None) -> None:
        super().__init__(parent)
        self.tr_text = language.tr if language else lambda key, **_: key
        self.setWindowTitle(self.tr_text("font.browser"))
        self.resize(580, 560)
        self.records = [row if isinstance(row, dict) else {"family": row, "supported_languages": []} for row in fonts]
        self.project_fonts = set(project_fonts or [])
        self.recommendations = recommendations or []
        self.preferences = FontPreferences(config) if config else None
        self.sample = (sample or self.tr_text("font.sample"))[:80]
        layout = QVBoxLayout(self)
        self.disclaimer = QLabel(self.tr_text("font.recommend_disclaimer"))
        self.disclaimer.setWordWrap(True)
        layout.addWidget(self.disclaimer)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr_text("font.search"))
        self.scope = QComboBox()
        for key in ("project", "recent", "favorites", "similar", "all"):
            self.scope.addItem(self.tr_text("font.scope_" + key), key)
        row.addWidget(self.search, 1)
        row.addWidget(self.scope)
        layout.addLayout(row)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        self.empty = QLabel("")
        layout.addWidget(self.empty)
        self.preview = QLabel(self.sample)
        self.preview.setMinimumHeight(82)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview)
        self.favorite_button = QPushButton(self.tr_text("font.favorite"))
        self.favorite_button.clicked.connect(self.toggle_favorite)
        layout.addWidget(self.favorite_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.refresh)
        self.scope.currentIndexChanged.connect(self.refresh)
        self.list.currentItemChanged.connect(self.preview_font)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self.scope.setCurrentIndex(4)
        self.refresh()
        for index in range(self.list.count()):
            if self.list.item(index).data(Qt.ItemDataRole.UserRole) == current:
                self.list.setCurrentRow(index)
                break

    def refresh(self, *_args) -> None:
        current = self.selected()
        query = self.search.text().casefold().strip()
        scope = self.scope.currentData()
        recent = set(self.preferences.recent if self.preferences else [])
        favorites = set(self.preferences.favorites if self.preferences else [])
        recommended = {r["family"]: r["similarity"] for r in self.recommendations}
        self.list.clear()
        for record in self.records:
            family = record["family"]
            if query not in family.casefold():
                continue
            if (scope == "project" and family not in self.project_fonts or
                scope == "recent" and family not in recent or
                scope == "favorites" and family not in favorites or
                scope == "similar" and family not in recommended):
                continue
            marker = "★ " if family in favorites else ""
            match = " · " + self.tr_text("font.match_" + recommended[family]) if family in recommended else ""
            item = QListWidgetItem(f"{marker}{family}{match}\n{self.sample}")
            item.setData(Qt.ItemDataRole.UserRole, family)
            item.setFont(QFont(family, 12))
            item.setToolTip(record.get("file_path", family))
            self.list.addItem(item)
            if family == current:
                self.list.setCurrentItem(item)
        self.empty.setText(self.tr_text("font.empty_favorites") if scope == "favorites" and not self.list.count()
                           else self.tr_text("font.no_results") if not self.list.count() else "")

    def preview_font(self, item, _previous=None) -> None:
        family = item.data(Qt.ItemDataRole.UserRole) if item else ""
        if family:
            self.preview.setFont(QFont(family, 24))
            self.preview_changed.emit(family)

    def toggle_favorite(self) -> None:
        family = self.selected()
        if family and self.preferences:
            self.preferences.toggle_favorite(family)
            self.refresh()

    def selected(self) -> str:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""
