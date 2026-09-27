"""Deterministic Chinese text fitting shared by preview, export and checks."""
from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtGui import QFont, QFontMetrics

FORBIDDEN_START = set("，。！？：；、）】》〉”’,.!?;:")
FORBIDDEN_END = set("（【《〈“‘")


@dataclass(frozen=True)
class LayoutResult:
    font: QFont
    lines: list[str]
    status: str
    occupied_height: float
    occupied_width: float
    padding: tuple[float, float, float, float]


def _font(style: dict, size: int) -> QFont:
    font = QFont(style.get("font", "Microsoft YaHei"), size)
    font.setBold(bool(style.get("bold", False)))
    font.setItalic(bool(style.get("italic", False)))
    weight = style.get("font_weight")
    if weight is not None:
        font.setWeight(QFont.Weight(max(1, min(1000, int(weight)))))
    spacing = float(style.get("letter_spacing", 0))
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def wrap_chinese(text: str, metrics: QFontMetrics, width: float) -> list[str]:
    """Wrap measured glyphs while keeping opening/closing punctuation off forbidden line edges."""
    width = max(1, width)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            if current and metrics.horizontalAdvance(current + char) > width:
                if char in FORBIDDEN_START and len(current) > 1:
                    lines.append(current[:-1])
                    current = current[-1] + char
                elif char in FORBIDDEN_START:
                    current += char
                else:
                    if current[-1] in FORBIDDEN_END and len(current) > 1:
                        lines.append(current[:-1])
                        current = current[-1] + char
                    else:
                        lines.append(current)
                        current = char
            else:
                current += char
        lines.append(current)
    return lines


def fit_layout(text: str, style: dict, box_width: float, box_height: float) -> LayoutResult:
    """Choose a bounded font size for the padded box; return overflow rather than shrinking indefinitely."""
    pad = float(style.get("padding", 8))
    top = float(style.get("padding_top", pad))
    right = float(style.get("padding_right", pad))
    bottom = float(style.get("padding_bottom", pad))
    left = float(style.get("padding_left", pad))
    available_width = max(1.0, box_width - left - right)
    available_height = max(1.0, box_height - top - bottom)
    minimum = max(6, int(style.get("min_size", 18)))
    maximum = min(300, int(style.get("max_size", 72)))
    if minimum > maximum:
        raise ValueError("Minimum font size exceeds maximum")
    spacing = max(.5, min(3.0, float(style.get("line_spacing", 1))))
    vertical = style.get("writing_mode") == "vertical"

    def measure(size: int):
        font = _font(style, size)
        metrics = QFontMetrics(font)
        if vertical:
            chars_per_column = max(1, int(available_height // max(1, metrics.height() * spacing)))
            columns: list[str] = []
            for paragraph in text.split("\n"):
                columns.extend(paragraph[i:i+chars_per_column]
                               for i in range(0, len(paragraph), chars_per_column))
            columns = columns or [""]
            occupied_width = len(columns) * max(metrics.maxWidth(), size) * spacing
            occupied_height = max((len(col) for col in columns), default=0) * metrics.height() * spacing
            return font, columns, occupied_width, occupied_height
        lines = wrap_chinese(text, metrics, available_width)
        occupied_width = max((metrics.horizontalAdvance(line) for line in lines), default=0)
        occupied_height = len(lines) * metrics.lineSpacing() * spacing
        return font, lines, occupied_width, occupied_height

    best = None
    low, high = minimum, maximum
    while low <= high:
        size = (low + high) // 2
        measured = measure(size)
        if measured[2] <= available_width and measured[3] <= available_height:
            best = measured
            low = size + 1
        else:
            high = size - 1
    if best is None:
        best = measure(minimum)
    _, lines, used_width, used_height = best
    if used_width > available_width or used_height > available_height:
        status = "overflow"
    elif max(used_width / available_width, used_height / available_height) > .9:
        status = "warning"
    else:
        status = "fit"
    return LayoutResult(best[0], lines, status, used_height / available_height,
                        used_width / available_width, (top, right, bottom, left))
