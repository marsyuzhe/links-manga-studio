"""Consistent outline icons rendered from SVG paths at display resolution."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m3 17 5-5 4 4 3-3 6 6"/>',
    "folder": '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "pdf": '<path d="M6 2h9l5 5v14H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M15 2v5h5M8 16h8M8 12h6"/>',
    "ocr": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 10h10M9 14h6M7 7v2M17 15v2"/>',
    "text": '<path d="M4 6h16M12 6v14M8 20h8M7 6l-2 4M17 6l2 4"/>',
    "erase": '<path d="m4 15 9-10a2 2 0 0 1 3 0l5 5a2 2 0 0 1 0 3l-7 7H8zM4 15l5 5M12 20h9"/>',
    "export": '<path d="M12 3v13m-5-5 5 5 5-5M4 17v3h16v-3"/>',
    "pointer": '<path d="M5 2v18l5-5 3 7 3-1-3-7h7z"/>',
    "hand": '<path d="M7 13V7a2 2 0 0 1 4 0v4-7a2 2 0 0 1 4 0v7-5a2 2 0 0 1 4 0v9c0 4-3 6-7 6H9c-2 0-4-1-5-3l-2-4a2 2 0 0 1 3-2z"/>',
    "mask": '<path d="M12 3c5 0 9 4 9 9s-4 9-9 9-9-4-9-9 4-9 9-9zM12 3v18"/>',
    "zoom": '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M7 10h6M10 7v6"/>',
    "previous": '<path d="m15 5-7 7 7 7"/>',
    "next": '<path d="m9 5 7 7-7 7"/>',
    "fit": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "add": '<path d="M12 4v16M4 12h16"/>',
    "minus": '<path d="M4 12h16"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
}


def icon(name: str, color: str = "#A8AFBD", size: int = 20) -> QIcon:
    body = PATHS[name]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
