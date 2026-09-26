import json

from PySide6.QtGui import QImage
from PIL import Image, ImageDraw, ImageFont

from app.importers.folder_importer import scan_files
from app.importers.image_importer import ImageImporter
from app.ocr.pipeline import ModelManager, OCRPipeline, RapidBackend
from app.ocr.tasks import run_ocr_task
from app.pages.page_service import PageService


class FakeBackend:
    name = "FixtureOCR"
    model = "fixture"

    def __init__(self):
        self.text = "HELLO"
        self.x = 20

    def recognize(self, image):
        x = self.x
        return [{"polygon": [[x, 20], [x+100, 20], [x+100, 70], [x, 70]],
                 "text": self.text, "confidence": .9}]


def test_ocr_raw_uid_stability_and_reocr(project_factory, tmp_path):
    project = project_factory()
    path = tmp_path / "page.png"
    image = QImage(300, 200, QImage.Format.Format_RGB32)
    image.fill("white")
    assert image.save(str(path))
    importer = ImageImporter(project.path)
    assert importer.commit(importer.validate(scan_files([path]))) == 1
    page = PageService(project.connection, project.path).list_pages()[0]
    fake = FakeBackend()
    pipeline = OCRPipeline(project.connection, project.path, fake)
    assert pipeline.process_page(page) == 1
    first = project.connection.execute("SELECT id,text_uid,bbox_json FROM text_blocks").fetchone()
    assert first["text_uid"] == "P0001-T001"
    fake.text = "WORLD"
    fake.x = 25
    assert pipeline.process_page(page) == 1
    rows = project.connection.execute("SELECT id,text_uid,source_text,active FROM text_blocks").fetchall()
    assert len(rows) == 1 and rows[0]["id"] == first["id"] and rows[0]["source_text"] == "WORLD"
    fake.x = 170
    assert pipeline.process_page(page) == 1
    assert [r[0] for r in project.connection.execute("SELECT text_uid FROM text_blocks ORDER BY text_uid")] == [
        "P0001-T001", "P0001-T002"]
    assert project.connection.execute("SELECT COUNT(*) FROM ocr_runs").fetchone()[0] == 3
    raw = json.loads(project.connection.execute("SELECT raw_recognition_json FROM ocr_runs ORDER BY rowid DESC LIMIT 1").fetchone()[0])
    assert raw[0]["text"] == "WORLD"


def test_real_rapidocr_offline_sample(tmp_path):
    assert ModelManager().status()["installed"]
    sample = Image.new("RGB", (640, 180), "white")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 75)
    ImageDraw.Draw(sample).text((35, 35), "HELLO 123", fill="black", font=font)
    path = tmp_path / "sample.png"
    sample.save(path)
    image = QImage(str(path))
    backend = RapidBackend()
    result = backend.recognize(image)
    assert any("HELLO" in item["text"].upper().replace(" ", "") for item in result)


def test_real_ocr_task_commits_raw_results(project_factory, tmp_path):
    project = project_factory()
    sample = Image.new("RGB", (640, 180), "white")
    ImageDraw.Draw(sample).text((35, 35), "HELLO 123", fill="black",
                                font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 75))
    path = tmp_path / "sample.png"
    sample.save(path)
    importer = ImageImporter(project.path)
    importer.commit(importer.validate(scan_files([path])))
    page = PageService(project.connection, project.path).list_pages()[0]
    result = run_ocr_task(project.path, [page["id"]])
    assert result["status"] == "completed" and result["completed"] == 1
    assert project.connection.execute("SELECT COUNT(*) FROM ocr_runs").fetchone()[0] == 1
    text = project.connection.execute("SELECT source_text FROM text_blocks").fetchone()[0]
    assert "HELLO" in text.upper().replace(" ", "")
