"""Small real image fixtures shared by acceptance tests."""
from pathlib import Path
import pytest
from PySide6.QtGui import QColor, QImage
from app.config import Config
from app.project import ProjectService


def make_image(path: Path, width: int = 128, height: int = 192, seed: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor.fromHsv(seed % 360, 80, 240))
    image.setPixelColor(0, 0, QColor(seed % 256, (seed // 256) % 256, 20))
    assert image.save(str(path))
    return path


@pytest.fixture
def project_factory(tmp_path):
    services = []
    def create(name="测试漫画", mode="copy"):
        service = ProjectService(Config(tmp_path / "config.json"))
        service.create_project(tmp_path, name, mode)
        services.append(service)
        return service
    yield create
    for service in services:
        service.close_project()
