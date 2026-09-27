"""Original-coordinate comic canvas with bounded view transforms."""
import math
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView
from app.themes import DARK


class BlockItem(QGraphicsRectItem):
    def __init__(self, block_id: str, rect, canvas, erased: bool = False) -> None:
        super().__init__(*rect)
        self.block_id = block_id
        self.canvas = canvas
        self.erased = erased
        self._hovered = False
        self.setPen(QPen(QColor(canvas.tokens["warning"] if erased else canvas.tokens["overlay_idle"]), 1))
        self.setToolTip(block_id)
        self.setZValue(2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        self.setTransformOriginPoint(self.rect().center())
        self._edit_mode = None
        self._start_rect = None
        self._start_pos = None
        self._start_rotation = None

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-12, -18, 12, 12)

    def paint(self, painter, option, widget=None) -> None:
        tokens = self.canvas.tokens
        painter.setPen(QPen(QColor(tokens["overlay_selected"]) if self.isSelected()
                            else QColor(tokens["border_strong"] if self._hovered else tokens["overlay_idle"]), 2 if self.isSelected() else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())
        if self.isSelected():
            painter.setPen(QPen(QColor(tokens["accent_text"]), 1))
            painter.setBrush(QColor(tokens["overlay_selected"]))
            rect = self.rect()
            for x in (rect.left(), rect.center().x(), rect.right()):
                for y in (rect.top(), rect.center().y(), rect.bottom()):
                    if (x, y) != (rect.center().x(), rect.center().y()):
                        painter.drawRect(QRectF(x-3, y-3, 6, 6))
            painter.setBrush(QColor(tokens["warning"]))
            painter.drawEllipse(QRectF(rect.center().x()-4, rect.top()-15, 8, 8))

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event) -> None:
        rect = self.rect()
        if self.isSelected() and (event.pos() - rect.bottomRight()).manhattanLength() < 12:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self.isSelected() and (event.pos() - self._rotation_handle()).manhattanLength() < 12:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.setSelected(True)
        self.canvas.block_selected.emit(self.block_id)
        if self.canvas.text_tool and self.erased:
            self.canvas.block_edit_requested.emit(self.block_id)
            event.accept()
            return
        rect = self.rect()
        self._start_rect = QRectF(rect)
        self._start_pos = self.pos()
        self._start_rotation = self.rotation()
        if (event.pos() - rect.bottomRight()).manhattanLength() < 12:
            self._edit_mode = "resize"
            event.accept()
        elif (event.pos() - self._rotation_handle()).manhattanLength() < 12:
            self._edit_mode = "rotate"
            event.accept()
        else:
            self._edit_mode = "move"
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._edit_mode == "resize":
            rect = self.rect()
            self.setRect(rect.x(), rect.y(), max(10, event.pos().x()-rect.x()),
                         max(10, event.pos().y()-rect.y()))
            event.accept()
        elif self._edit_mode == "rotate":
            center = self.mapToScene(self.rect().center())
            delta = event.scenePos() - center
            self.setRotation(math.degrees(math.atan2(delta.y(), delta.x())) + 90)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._edit_mode == "move":
            super().mouseReleaseEvent(event)
        if self._edit_mode and (self.rect() != self._start_rect or self.pos() != self._start_pos
                                or self.rotation() != self._start_rotation):
            rect = self.rect()
            sx, sy = self.canvas.block_scale
            box = [(rect.left()+self.pos().x())/sx, (rect.top()+self.pos().y())/sy,
                   (rect.right()+self.pos().x())/sx, (rect.bottom()+self.pos().y())/sy]
            self.canvas.block_changed.emit(self.block_id, box, self.rotation())
        self._edit_mode = None
        event.accept()

    def _rotation_handle(self):
        rect = self.rect()
        return QPointF(rect.center().x(), rect.top() - 11)

    def mouseDoubleClickEvent(self, event) -> None:
        self.canvas.block_double_clicked.emit(self.block_id)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.canvas.block_context_requested.emit(self.block_id, event.screenPos())
        event.accept()


class ComicCanvas(QGraphicsView):
    zoom_changed = Signal(float)
    block_selected = Signal(str)
    block_edit_requested = Signal(str)
    block_double_clicked = Signal(str)
    block_changed = Signal(str, object, float)
    block_context_requested = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.tokens = DARK
        self.setBackgroundBrush(QColor(self.tokens["canvas_bg"]))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._space = False
        self._drag_position = None
        self._has_image = False
        self.fit_mode = True
        self.page_id = None
        self.text_tool = False
        self.hand_tool = False
        self.block_items = {}
        self.block_scale = (1.0, 1.0)
        self._font_preview_items = []

    def set_theme(self, tokens) -> None:
        self.tokens = tokens
        self.setBackgroundBrush(QColor(tokens["canvas_bg"]))
        if self._has_image and hasattr(self,"page_border"):
            pen=QPen(QColor(tokens["panel_border"]),1)
            pen.setCosmetic(True)
            self.page_border.setPen(pen)
        self.viewport().update()

    def message(self, text: str) -> None:
        self.clear_font_preview()
        self.scene().clear()
        self.block_items.clear()
        self._has_image = False
        self.page_id = None
        self.resetTransform()
        item = self.scene().addText(text)
        item.setDefaultTextColor(QColor(self.tokens["text_primary"]))
        self.scene().setSceneRect(item.boundingRect())

    def show_image(self, page_id: str, image: QImage) -> None:
        self.clear_font_preview()
        self.scene().clear()
        self.block_items.clear()
        shade = QColor(self.tokens["shadow"])
        shade.setAlpha(38)
        shadow = self.scene().addRect(5, 6, image.width(), image.height(),
                                      QPen(Qt.PenStyle.NoPen), shade)
        shadow.setZValue(-1)
        self.scene().addPixmap(QPixmap.fromImage(image))
        page_pen=QPen(QColor(self.tokens["panel_border"]),1)
        page_pen.setCosmetic(True)
        self.page_border=self.scene().addRect(0,0,image.width(),image.height(),page_pen)
        self.page_border.setZValue(1)
        self.scene().setSceneRect(0, 0, image.width(), image.height())
        self._has_image = True
        self.page_id = page_id
        self.fit()

    def show_blocks(self, blocks: list[dict], page_width: float, page_height: float) -> None:
        if not self._has_image or not page_width or not page_height:
            return
        import json
        rect = self.sceneRect()
        sx, sy = rect.width() / page_width, rect.height() / page_height
        self.block_scale = (sx, sy)
        for block in blocks:
            x0, y0, x1, y1 = json.loads(block["bbox_json"])
            item = BlockItem(block["id"], (x0*sx, y0*sy, (x1-x0)*sx, (y1-y0)*sy), self,
                             block.get("erase_status") == "erased")
            item.setRotation(float(block.get("rotation") or 0))
            self.scene().addItem(item)
            self.block_items[block["id"]] = item

    def select_block(self, block_id: str) -> None:
        for key, item in self.block_items.items():
            item.setSelected(key == block_id)
        if block_id in self.block_items:
            self.centerOn(self.block_items[block_id])

    def preview_font(self, block_id: str, family: str, text: str) -> None:
        self.clear_font_preview()
        item = self.block_items.get(block_id)
        if not item or not text:
            return
        rect = item.sceneBoundingRect()
        backing = self.scene().addRect(rect, QPen(Qt.PenStyle.NoPen), QColor("#ffffff"))
        backing.setZValue(5)
        preview = self.scene().addText(text, QFont(family, max(8, int(min(rect.height()/3, 34)))))
        preview.setDefaultTextColor(QColor("#111111"))
        preview.setTextWidth(max(10, rect.width()-8))
        preview.setPos(rect.left()+4, rect.top()+4)
        preview.setZValue(6)
        self._font_preview_items = [backing, preview]

    def clear_font_preview(self) -> None:
        for item in self._font_preview_items:
            if item.scene():
                self.scene().removeItem(item)
        self._font_preview_items = []

    def fit(self) -> None:
        self.fit_mode = True
        if self._has_image:
            rect = self.sceneRect()
            scale = min((self.viewport().width()-4)/rect.width(), (self.viewport().height()-4)/rect.height())
            self.set_zoom(scale, fit=True)
            self.centerOn(rect.center())

    def set_zoom(self, value: float, fit: bool = False) -> None:
        self.fit_mode = fit
        value = max(.05, min(16.0, value))
        self.resetTransform()
        self.scale(value, value)
        self.zoom_changed.emit(value)

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self.transform().m11() * factor)

    def set_hand_tool(self, enabled: bool) -> None:
        self.hand_tool = enabled
        self.setCursor(Qt.CursorShape.OpenHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event) -> None:
        self.zoom_by(1.2 if event.angleDelta().y() > 0 else 1/1.2)
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space = False
            self.unsetCursor()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._space = False
        self._drag_position = None
        self.unsetCursor()
        super().focusOutEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or ((self._space or self.hand_tool) and event.button() == Qt.MouseButton.LeftButton):
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None:
            delta = event.position() - self._drag_position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-int(delta.y()))
            self._drag_position = event.position()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_position = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if self._space or self.hand_tool else Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.fit_mode:
            self.fit()
