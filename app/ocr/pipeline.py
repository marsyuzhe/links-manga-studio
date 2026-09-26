"""Offline OCR with raw-result preservation and stable Text UIDs."""
from __future__ import annotations

import importlib.metadata
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Protocol

from PySide6.QtGui import QImage

from app.images.image_loader import ImageLoader
from app.pdf.render import PdfRenderService


class OCRBackend(Protocol):
    name: str
    model: str

    def recognize(self, image: QImage) -> list[dict]: ...


class ModelManager:
    """Inspect installed model files without downloading at application startup."""
    REQUIRED = ("PP-OCRv6_det_small.onnx", "PP-OCRv6_rec_small.onnx",
                "ch_ppocr_mobile_v2.0_cls_mobile.onnx")

    def __init__(self, model_dir: Path | None = None) -> None:
        if model_dir is None:
            import rapidocr
            model_dir = Path(rapidocr.__file__).parent / "models"
        self.model_dir = model_dir

    def status(self) -> dict:
        missing = [name for name in self.REQUIRED if not (self.model_dir / name).is_file()]
        return {"path": str(self.model_dir), "installed": not missing, "missing": missing,
                "engine": "RapidOCR", "version": importlib.metadata.version("rapidocr"),
                "model": "PP-OCRv6-small", "device": "CPU"}


class RapidBackend:
    name = "RapidOCR"
    model = "PP-OCRv6-small"

    def __init__(self, models: ModelManager | None = None) -> None:
        self.models = models or ModelManager()
        status = self.models.status()
        if not status["installed"]:
            raise FileNotFoundError(f"Missing OCR model files: {', '.join(status['missing'])}; select a model folder")
        from rapidocr import RapidOCR
        self.engine = RapidOCR(params={
            "Det.model_path": str(self.models.model_dir / "PP-OCRv6_det_small.onnx"),
            "Rec.model_path": str(self.models.model_dir / "PP-OCRv6_rec_small.onnx"),
            "Cls.model_path": str(self.models.model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
            "Global.use_cls": False,
        })

    def recognize(self, image: QImage) -> list[dict]:
        import numpy as np
        rgb = image.convertToFormat(QImage.Format.Format_RGB888)
        array = np.frombuffer(rgb.bits(), dtype=np.uint8).reshape(rgb.height(), rgb.bytesPerLine())
        array = array[:, :rgb.width() * 3].reshape(rgb.height(), rgb.width(), 3).copy()
        result = self.engine(array)
        if result.boxes is None:
            return []
        return [{"polygon": box.tolist(), "text": text, "confidence": float(score)}
                for box, text, score in zip(result.boxes, result.txts, result.scores)]


def overlap(a: list[float], b: list[float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x1-x0) * max(0, y1-y0)
    areas = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / areas if areas > 0 else 0


class OCRPipeline:
    def __init__(self, connection: sqlite3.Connection, project: Path, backend: OCRBackend | None = None) -> None:
        self.db = connection
        self.project = project
        self.backend = backend

    def process_page(self, page: dict, dpi: int = 250) -> int:
        backend = self.backend or RapidBackend()
        start = time.perf_counter()
        if page.get("source_kind") == "pdf":
            image = PdfRenderService(self.project).render(page, dpi, "ocr")
        else:
            image = ImageLoader().load(Path(page["path"]))
        raw = backend.recognize(image)
        sx, sy = page["width"] / image.width(), page["height"] / image.height()
        normalized = []
        for item in raw:
            polygon = [[round(float(x) * sx, 3), round(float(y) * sy, 3)] for x, y in item["polygon"]]
            xs, ys = [point[0] for point in polygon], [point[1] for point in polygon]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            normalized.append((item, polygon, bbox))
        direction = self.db.execute("SELECT reading_direction FROM projects").fetchone()[0]
        normalized.sort(key=lambda part: (part[2][1], -part[2][0] if direction == "japanese" else part[2][0]))
        existing = self.db.execute("SELECT * FROM text_blocks WHERE page_id=? AND active=1", (page["id"],)).fetchall()
        used: set[str] = set()
        max_number = max((int(row["text_uid"].rsplit("-T", 1)[-1]) for row in
                          self.db.execute("SELECT text_uid FROM text_blocks WHERE page_id=?", (page["id"],))), default=0)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        elapsed = round((time.perf_counter() - start) * 1000)
        with self.db:
            self.db.execute("""INSERT INTO ocr_runs
                (id,page_id,engine,engine_version,model,model_version,parameters_json,
                 raw_detection_json,raw_recognition_json,processing_ms,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (str(uuid.uuid4()), page["id"], backend.name,
                importlib.metadata.version("rapidocr") if backend.name == "RapidOCR" else "test",
                backend.model, "v6" if backend.name == "RapidOCR" else "test",
                json.dumps({"dpi": dpi, "device": "CPU", "render_size": [image.width(), image.height()]}),
                json.dumps([entry["polygon"] for entry in raw]), json.dumps(raw, ensure_ascii=False),
                elapsed, timestamp))
            # Free sequence numbers without colliding with inactive rows from older OCR runs.
            temporary = self.db.execute("SELECT MIN(sequence) FROM text_blocks WHERE page_id=?", (page["id"],)).fetchone()[0]
            temporary = min(0, temporary or 0)
            for row in existing:
                temporary -= 1
                self.db.execute("UPDATE text_blocks SET sequence=? WHERE id=?", (temporary, row["id"]))
            for sequence, (item, polygon, bbox) in enumerate(normalized, 1):
                candidates = [(overlap(json.loads(row["bbox_json"]), bbox), row) for row in existing
                              if row["id"] not in used]
                score, matched = max(candidates, key=lambda pair: pair[0], default=(0, None))
                if score >= .5 and matched is not None:
                    used.add(matched["id"])
                    self.db.execute("""UPDATE text_blocks SET sequence=?,reading_order=?,bbox_json=?,polygon_json=?,
                        source_text=?,ocr_confidence=?,revision=revision+1 WHERE id=?""",
                        (sequence, sequence, json.dumps(bbox), json.dumps(polygon), item["text"],
                         item["confidence"], matched["id"]))
                else:
                    max_number += 1
                    self.db.execute("""INSERT INTO text_blocks
                        (id,page_id,text_uid,sequence,reading_order,bbox_json,polygon_json,source_text,ocr_confidence)
                        VALUES(?,?,?,?,?,?,?,?,?)""", (str(uuid.uuid4()), page["id"],
                        f"{page['page_uid']}-T{max_number:03d}", sequence, sequence,
                        json.dumps(bbox), json.dumps(polygon), item["text"], item["confidence"]))
            for row in existing:
                if row["id"] not in used:
                    self.db.execute("UPDATE text_blocks SET active=0 WHERE id=?", (row["id"],))
        return len(normalized)
