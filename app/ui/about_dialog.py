"""Compact product identity and local support information."""
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import __version__
from app.branding import DISPLAY_NAME, AUTHOR_EN, TAGLINE_EN


class AboutDialog(QDialog):
    def __init__(self, host):
        super().__init__(host)
        zh = host.language.language == "zh_CN"
        self.setWindowTitle("关于" if zh else "About")
        self.setFixedSize(460, 310)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel(DISPLAY_NAME)
        title.setProperty("role", "title")
        layout.addWidget(title)
        layout.addWidget(QLabel(TAGLINE_EN))
        author = QLabel(f"Created by {AUTHOR_EN}")
        author.setProperty("role", "muted")
        layout.addWidget(author)
        self.version_label = QLabel(f"Version {__version__}   ·   Windows Portable")
        self.version_label.setProperty("role", "muted")
        layout.addWidget(self.version_label)
        layout.addStretch(1)
        actions = QHBoxLayout()
        self.diagnostics_button = QPushButton("环境诊断" if zh else "Diagnostics")
        self.diagnostics_button.clicked.connect(host.show_diagnostics)
        self.logs_button = QPushButton("打开日志" if zh else "Open logs")
        self.logs_button.clicked.connect(host.open_log_action.trigger)
        self.license_button = QPushButton("第三方许可证" if zh else "Third-party licenses")
        self.license_path = (Path(sys.executable).resolve().parent / "licenses" if getattr(sys, "frozen", False)
                             else Path(__file__).resolve().parents[2] / "licenses")
        self.license_button.setEnabled(self.license_path.exists())
        self.license_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.license_path))))
        for button in (self.license_button, self.diagnostics_button, self.logs_button):
            actions.addWidget(button)
        layout.addLayout(actions)
