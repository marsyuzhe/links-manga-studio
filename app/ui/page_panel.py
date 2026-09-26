"""Virtual page list with bounded thumbnail pixmaps."""
from collections import OrderedDict
from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyledItemDelegate
from app.themes import DARK


class PageRowDelegate(QStyledItemDelegate):
    """Compact thumbnail rows with a quiet selection indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tokens = DARK

    def paint(self, painter, option, index):
        page = index.model().pages[index.row()]
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        tokens = self.tokens
        painter.fillRect(rect, QColor(tokens["selected_bg"] if selected else tokens["hover_bg"] if hover else tokens["panel_bg"]))
        if selected:
            painter.fillRect(QRect(rect.x(), rect.y()+5, 3, rect.height()-10), QColor(tokens["accent"]))
        pixmap = index.model().data(index, Qt.ItemDataRole.DecorationRole)
        thumb = QRect(rect.x()+12, rect.y()+7, 59, rect.height()-14)
        painter.fillRect(thumb, QColor(tokens["page_placeholder"]))
        if isinstance(pixmap, QPixmap):
            image = pixmap.scaled(thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(thumb.x()+(thumb.width()-image.width())//2,
                               thumb.y()+(thumb.height()-image.height())//2, image)
        x = rect.x()+82
        painter.setPen(QColor(tokens["page_ink"]))
        font = QFont(option.font)
        font.setPointSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        number = f"{index.row()+1:03d}"
        if not index.model().simple_mode:
            number += f"  {page['page_uid']}"
        painter.drawText(QRect(x, rect.y()+13, rect.width()-x+rect.x()-9, 24),
                         Qt.AlignmentFlag.AlignVCenter, number)
        painter.setPen(QColor(tokens["page_secondary"]))
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        count = page.get("text_count", 0)
        ocr = "OCR ✓" if count else "OCR ·"
        painter.drawText(QRect(x, rect.y()+41, rect.width()-x+rect.x()-9, 18),
                         Qt.AlignmentFlag.AlignVCenter, ocr)
        progress = f"译 {page.get('translated_count', 0)}/{count}  ·  字 {page.get('typeset_count', 0)}/{count}"
        if index.model().language.language == "en_US":
            progress = f"Tr {page.get('translated_count', 0)}/{count}  ·  Set {page.get('typeset_count', 0)}/{count}"
        painter.drawText(QRect(x, rect.y()+60, rect.width()-x+rect.x()-9, 18),
                         Qt.AlignmentFlag.AlignVCenter, progress)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(230, 94)


class PageListModel(QAbstractListModel):
    def __init__(self, language, parent=None) -> None:
        super().__init__(parent)
        self.language = language
        self.tokens = DARK
        self.simple_mode = True
        self.pages: list[dict] = []
        self.pixmaps: OrderedDict[str, QPixmap] = OrderedDict()
        self.placeholder = QPixmap(64, 88)
        self.placeholder.fill(QColor(self.tokens["page_placeholder"]))
        painter = QPainter(self.placeholder)
        painter.setPen(QColor(self.tokens["text_muted"]))
        painter.drawText(self.placeholder.rect(), Qt.AlignmentFlag.AlignCenter, self.language.tr("status.loading"))
        painter.end()

    def retranslate(self) -> None:
        painter = QPainter(self.placeholder)
        painter.fillRect(self.placeholder.rect(), QColor(self.tokens["page_placeholder"]))
        painter.setPen(QColor(self.tokens["text_muted"]))
        painter.drawText(self.placeholder.rect(), Qt.AlignmentFlag.AlignCenter, self.language.tr("status.loading"))
        painter.end()
        if self.pages:
            self.dataChanged.emit(self.index(0), self.index(len(self.pages)-1))

    def set_theme(self, tokens):
        self.tokens = tokens
        self.retranslate()

    def set_pages(self, pages: list[dict]) -> None:
        self.beginResetModel()
        self.pages = pages
        self.pixmaps.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.pages)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.pages):
            return None
        page = self.pages[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            state = self.language.tr(f"status.{page['status']}") if page["status"] in ("missing", "broken") else ""
            count = page.get("text_count", 0)
            progress = (f"OCR {'✓' if count else '·'} · {self.language.tr('panel.translation')} {page.get('translated_count', 0)}/{count}"
                        f" · {self.language.tr('panel.typeset')} {page.get('typeset_count', 0)}/{count}") if count else "OCR —"
            heading = str(index.row()+1) if self.simple_mode else f"{index.row()+1}  {page['page_uid']}"
            return f"{heading}\n{progress}  {state}"
        if role == Qt.ItemDataRole.DecorationRole:
            pixmap = self.pixmaps.get(page["id"])
            if pixmap is not None:
                self.pixmaps.move_to_end(page["id"])
                return pixmap
            return self.placeholder
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(240, 100)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{page['filename']}\n{page['path']}"
        return None

    def thumbnail_ready(self, page_id: str, image: QImage | None, status: str) -> None:
        row = next((i for i, p in enumerate(self.pages) if p["id"] == page_id), None)
        if row is None:
            return
        self.pages[row]["status"] = status or "ready"
        if image is not None:
            self.pixmaps[page_id] = QPixmap.fromImage(image).scaled(64, 88, Qt.AspectRatioMode.KeepAspectRatio,
                                                                 Qt.TransformationMode.SmoothTransformation)
            self.pixmaps.move_to_end(page_id)
            while len(self.pixmaps) > 64:
                self.pixmaps.popitem(last=False)
        self.dataChanged.emit(self.index(row), self.index(row))
