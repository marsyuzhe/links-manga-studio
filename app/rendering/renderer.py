"""Render source, masks, erase and translated text in one page coordinate space."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen

from app.images.image_loader import ImageLoader
from app.pdf.render import PdfRenderService
from app.rendering.layout import fit_layout, wrap_chinese
from app.styles.project_styles import ProjectStyleService


FORBIDDEN_LINE_START = set("，。！？：；）】》、,.!?;:")


def wrapped_lines(text: str, metrics: QFontMetrics, width: int) -> list[str]:
    return wrap_chinese(text, metrics, width)


def fit_font(text: str, family: str, width: int, height: int, minimum: int = 8, maximum: int = 72):
    best = minimum
    best_lines = [text]
    while minimum <= maximum:
        middle = (minimum + maximum) // 2
        font = QFont(family, middle)
        metrics = QFontMetrics(font)
        lines = wrapped_lines(text, metrics, max(1, width))
        if len(lines) * metrics.lineSpacing() <= height and all(metrics.horizontalAdvance(line) <= width for line in lines):
            best, best_lines = middle, lines
            minimum = middle + 1
        else:
            maximum = middle - 1
    return QFont(family, best), best_lines


class PageRenderer:
    """Compose an output image from immutable sources and persisted edits; never rewrite sources."""
    def __init__(self, connection: sqlite3.Connection, project: Path) -> None:
        self.db = connection
        self.project = project
        self.styles = ProjectStyleService(connection)

    def render_page(self, page: dict, pdf_dpi: int = 300, pdf_purpose: str = "ocr") -> QImage:
        if page.get("source_kind") == "pdf":
            image = PdfRenderService(self.project).render(page, pdf_dpi, pdf_purpose).convertToFormat(QImage.Format.Format_RGB888)
        else:
            image = ImageLoader().load(Path(page["path"])).convertToFormat(QImage.Format.Format_RGB888)
        rows = self.db.execute("""SELECT t.*,x.text AS translation,s.settings_json FROM text_blocks t
            LEFT JOIN translations x ON x.text_block_id=t.id AND x.language='zh_CN'
            LEFT JOIN styles s ON s.id=t.style_id WHERE t.page_id=? AND t.active=1
            ORDER BY t.reading_order""", (page["id"],)).fetchall()
        for row in rows:
            erase = json.loads(row["erase_data_json"])
            if erase or row["mask_path"]:
                image = self._erase(image, page, row, erase)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for row in rows:
            if row["translation"]:
                self._typeset(painter, image, page, row)
        painter.end()
        return image

    def _erase(self, image: QImage, page: dict, row, config: dict) -> QImage:
        mode = config.get("mode", "none")
        sx, sy = image.width() / page["width"], image.height() / page["height"]
        x0, y0, x1, y1 = json.loads(row["bbox_json"])
        x0, y0, x1, y1 = (round(x0*sx), round(y0*sy), round(x1*sx), round(y1*sy))
        if mode == "fill":
            painter = QPainter(image)
            painter.fillRect(x0, y0, x1-x0, y1-y0, QColor(config.get("color", "#ffffff")))
            painter.end()
            return image
        if mode not in ("telea", "ns") and not row["mask_path"]:
            return image
        mask = np.zeros((image.height(), image.width()), dtype=np.uint8)
        if row["mask_path"]:
            saved = QImage(str(self.project / row["mask_path"]))
            if not saved.isNull():
                saved = saved.convertToFormat(QImage.Format.Format_Grayscale8).scaled(image.width(), image.height())
                mask = np.frombuffer(saved.bits(), dtype=np.uint8).reshape(saved.height(), saved.bytesPerLine())[:, :saved.width()].copy()
        else:
            mask[max(0,y0):min(image.height(),y1), max(0,x0):min(image.width(),x1)] = 255
        rgb = np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width()*3]
        bgr = cv2.cvtColor(rgb.reshape(image.height(), image.width(), 3), cv2.COLOR_RGB2BGR)
        result = cv2.inpaint(bgr, mask, float(config.get("radius", 3)),
                             cv2.INPAINT_NS if mode == "ns" else cv2.INPAINT_TELEA)
        rgb_result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        return QImage(rgb_result.data, image.width(), image.height(), image.width()*3,
                      QImage.Format.Format_RGB888).copy()

    def _typeset(self, painter: QPainter, image: QImage, page: dict, row) -> None:
        style = self.styles.resolve(dict(row), json.loads(row["settings_json"] or "{}"))
        sx, sy = image.width() / page["width"], image.height() / page["height"]
        x0, y0, x1, y1 = json.loads(row["bbox_json"])
        x0, y0, x1, y1 = x0*sx, y0*sy, x1*sx, y1*sy
        layout = fit_layout(row["translation"], style, x1-x0, y1-y0)
        font, lines = layout.font, layout.lines
        metrics = QFontMetrics(font)
        painter.save()
        painter.translate((x0+x1)/2, (y0+y1)/2)
        painter.rotate(float(style.get("rotation", row["rotation"])))
        painter.translate(-(x0+x1)/2, -(y0+y1)/2)
        painter.setOpacity(float(style.get("opacity", 1)))
        top_pad, right_pad, bottom_pad, left_pad = layout.padding
        total_height = len(lines) * metrics.lineSpacing() * float(style.get("line_spacing", 1))
        vertical_alignment = style.get("vertical_alignment", "center")
        baseline = (y0 + top_pad + metrics.ascent() if vertical_alignment == "top" else
                    y1 - bottom_pad - total_height + metrics.ascent() if vertical_alignment == "bottom" else
                    y0 + (y1-y0-total_height)/2 + metrics.ascent())
        color = QColor(style.get("color", "#000000"))
        stroke_width = float(style.get("stroke_width", 0))
        if style.get("writing_mode") == "vertical":
            column_width = max(metrics.maxWidth(), font.pointSize()) * float(style.get("line_spacing", 1))
            xpos = x1 - right_pad - column_width / 2
            for column in lines:
                ypos = y0 + top_pad + metrics.ascent()
                for char in column:
                    path = QPainterPath()
                    path.addText(xpos - metrics.horizontalAdvance(char)/2, ypos, font, char)
                    if stroke_width > 0:
                        painter.setPen(QPen(QColor(style.get("stroke", "#ffffff")), stroke_width))
                        painter.drawPath(path)
                    painter.fillPath(path, color)
                    ypos += metrics.height() * float(style.get("line_spacing", 1))
                xpos -= column_width
            painter.restore()
            return
        for line in lines:
            advance = metrics.horizontalAdvance(line)
            alignment = style.get("alignment", "center")
            xpos = x0+left_pad if alignment == "left" else x1-right_pad-advance if alignment == "right" else (x0+x1-advance)/2
            path = QPainterPath()
            path.addText(xpos, baseline, font, line)
            if stroke_width > 0:
                painter.setPen(QPen(QColor(style.get("stroke", "#ffffff")), stroke_width))
                painter.drawPath(path)
            painter.fillPath(path, color)
            baseline += metrics.lineSpacing() * float(style.get("line_spacing", 1))
        painter.restore()
