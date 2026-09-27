"""Local brush/erase mask editor; mask files never alter source images."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGraphicsScene, QGraphicsView,
                              QHBoxLayout, QPushButton, QSpinBox)


class MaskView(QGraphicsView):
    def __init__(self, source: QImage, mask: QImage | None = None) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.scene().addPixmap(QPixmap.fromImage(source))
        self.mask = mask if mask is not None and not mask.isNull() else QImage(source.size(), QImage.Format.Format_Grayscale8)
        if mask is None or mask.isNull():
            self.mask.fill(0)
        elif self.mask.size() != source.size():
            self.mask = self.mask.scaled(source.size())
        self.overlay = self.scene().addPixmap(QPixmap())
        self.overlay.setZValue(1)
        self.mode = "brush"
        self.brush_size = 20
        self.last = None
        self.drag = None
        self.update_overlay()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def update_overlay(self) -> None:
        gray = self.mask.convertToFormat(QImage.Format.Format_Grayscale8)
        alpha = np.frombuffer(gray.bits(), dtype=np.uint8).reshape(gray.height(), gray.bytesPerLine())[:, :gray.width()]
        rgba = np.empty((gray.height(), gray.width(), 4), dtype=np.uint8)
        rgba[:, :, 0] = 255
        rgba[:, :, 1] = 0
        rgba[:, :, 2] = 0
        rgba[:, :, 3] = np.where(alpha > 0, 100, 0)
        image = QImage(rgba.data, gray.width(), gray.height(), gray.width()*4, QImage.Format.Format_RGBA8888).copy()
        self.overlay.setPixmap(QPixmap.fromImage(image))

    def stroke(self, start, end) -> None:
        painter = QPainter(self.mask)
        painter.setPen(QPen(QColor("white" if self.mode == "brush" else "black"), self.brush_size,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(start, end)
        painter.end()
        self.update_overlay()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.drag = event.position()
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint()).toPoint()
            self.last = point
            self.stroke(point, point)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.drag is not None:
            delta = event.position() - self.drag
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
            self.drag = event.position()
            event.accept()
        elif self.last is not None:
            point = self.mapToScene(event.position().toPoint()).toPoint()
            self.stroke(self.last, point)
            self.last = point
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.last = self.drag = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        current = self.transform().m11()
        if .1 <= current * factor <= 10:
            self.scale(factor, factor)
        event.accept()


from .components import dialog_layout, localize_buttons


class MaskDialog(QDialog):
    def __init__(self, source: QImage, mask: QImage | None = None, parent=None) -> None:
        super().__init__(parent)
        language = getattr(parent, "language", None)
        tr = language.tr if language else lambda key: {"mask.title": "Mask Editor", "mask.brush": "Brush", "mask.erase": "Erase"}.get(key, key)
        self.setWindowTitle(tr("mask.title"))
        self.resize(900, 700)
        self.view = MaskView(source, mask)
        layout = dialog_layout(self)
        toolbar = QHBoxLayout()
        brush = QPushButton(tr("mask.brush"))
        erase = QPushButton(tr("mask.erase"))
        brush.clicked.connect(lambda: setattr(self.view, "mode", "brush"))
        erase.clicked.connect(lambda: setattr(self.view, "mode", "erase"))
        size = QSpinBox()
        size.setRange(1, 300)
        size.setValue(20)
        size.valueChanged.connect(lambda value: setattr(self.view, "brush_size", value))
        for widget in (brush, erase, size):
            toolbar.addWidget(widget)
        layout.addLayout(toolbar)
        layout.addWidget(self.view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        if language:
            localize_buttons(buttons, tr)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
