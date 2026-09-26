from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage

from app.ui.mask_editor import MaskView


def test_brush_and_erase_mask(qtbot):
    source = QImage(100, 100, QImage.Format.Format_RGB32)
    source.fill("white")
    view = MaskView(source)
    qtbot.addWidget(view)
    view.stroke(QPoint(20, 20), QPoint(40, 40))
    assert view.mask.pixelColor(30, 30).red() > 0
    view.mode = "erase"
    view.stroke(QPoint(20, 20), QPoint(40, 40))
    assert view.mask.pixelColor(30, 30).red() == 0
