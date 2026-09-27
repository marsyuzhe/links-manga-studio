"""Reproducible real-image/UI benchmark; writes a report, not estimated numbers."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication
from app.cache.image_cache import ImageCache
from app.config import Config
from app.images.image_loader import ImageLoader
from app.importers.folder_importer import scan_folder
from app.importers.image_importer import ImageImporter
from app.logging_setup import setup_logging
from app.project import ProjectService
from app.ui.window import MainWindow


def rss_mb() -> float:
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return round(counters.WorkingSetSize / 1024**2, 2)


def wait(app: QApplication, predicate, seconds: float = 30) -> None:
    deadline = time.perf_counter() + seconds
    while not predicate():
        app.processEvents()
        time.sleep(.002)
        if time.perf_counter() > deadline:
            raise TimeoutError("Benchmark UI did not reach expected state")
    app.processEvents()


def main(report_destination: str | None = None) -> None:
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    if font_id < 0:
        raise RuntimeError("Benchmark requires an installed font with Latin digits")
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    root = Path(__file__).resolve().parents[1]
    output = root / "dev_data" / f"phase1-{uuid.uuid4().hex[:8]}"
    images = output / "漫画素材"
    images.mkdir(parents=True)
    for number in range(1, 1001):
        image = QImage(256, 384, QImage.Format.Format_RGB32)
        image.fill(QColor("#fffaf0"))
        painter = QPainter(image)
        painter.setPen(QColor("#182b49"))
        painter.setFont(QFont(family, 20))
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, f"PAGE {number:04d}")
        painter.end()
        image.setPixelColor(0, 0, QColor(number % 256, number // 256, 0))
        assert image.save(str(images / f"第{number:04d}页.png"))
    config = Config(output / "config.json")
    config.data["image_cache_mb"] = 16  # Explicit low-budget stress, default is 512.
    config.save()
    log = setup_logging(output / "logs")
    service = ProjectService(config)
    start = time.perf_counter()
    project = service.create_project(output, "千页测试", "reference")
    create_seconds = time.perf_counter() - start
    importer = ImageImporter(project)
    start = time.perf_counter()
    preview = importer.validate(scan_folder(images))
    validate_seconds = time.perf_counter() - start
    assert len(preview.candidates) == 1000 and not preview.errors
    start = time.perf_counter()
    assert importer.commit(preview) == 1000
    commit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    window = MainWindow(service, log)
    window.show()
    window._project_opened()
    app.processEvents()
    interactive_seconds = time.perf_counter() - start
    ws = window.workspace
    wait(app, lambda: not ws.jobs and ws.canvas.page_id == ws.current_id)
    app.processEvents()
    thumbnails_on_open = len(list((project / "cache/thumbnails").glob("*.png")))
    timings, samples = [], []
    for row in [0, 99, 199, 299, 399, 499, 599, 699, 799, 899, 999]:
        start = time.perf_counter()
        ws.panel.setCurrentIndex(ws.model.index(row))
        ws.panel.scrollTo(ws.model.index(row))
        wait(app, lambda: ws.canvas.page_id == ws.model.pages[row]["id"])
        timings.append((time.perf_counter()-start)*1000)
        samples.append({"page": row+1, "rss_mb": rss_mb(), "cache_mb": round(ws.cache.used_bytes/1024**2, 2)})
    for row in range(1000):
        ws.panel.setCurrentIndex(ws.model.index(row))
        wait(app, lambda: ws.canvas.page_id == ws.model.pages[row]["id"])
        if row in (99, 499, 999):
            samples.append({"sequential_page": row+1, "rss_mb": rss_mb(), "cache_mb": round(ws.cache.used_bytes/1024**2, 2)})
    assert ws.cache.used_bytes <= ws.cache.limit_bytes and ws.cache.evictions > 0
    assert len(ws.model.pixmaps) <= 64
    for row in range(50):
        ws.panel.setCurrentIndex(ws.model.index(row))
    wait(app, lambda: ws.canvas.page_id == ws.model.pages[49]["id"])
    ws.canvas.grab().save(str(output / "canvas.png"))
    evictions = ws.cache.evictions
    window.close()
    service.open_project(project)
    assert service.connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1000
    service.close_project()
    large_cache = ImageCache(128*1024**2)
    loader = ImageLoader()
    highres = []
    for index in range(3):
        path = output / f"highres_{index}.png"
        image = QImage(4000, 6000, QImage.Format.Format_RGB32)
        image.fill(QColor(index*40, 100, 200))
        assert image.save(str(path))
        del image
        start = time.perf_counter()
        decoded = loader.load(path)
        large_cache.put(str(path), decoded)
        highres.append({"dimensions": [decoded.width(), decoded.height()], "load_ms": round((time.perf_counter()-start)*1000, 2),
                        "rss_mb": rss_mb(), "cache_mb": round(large_cache.used_bytes/1024**2, 2)})
        del decoded
    assert large_cache.evictions == 2
    report = {"project_path": str(project), "source_path": str(images), "test_pages": 1000,
              "create_project_s": round(create_seconds, 3), "preflight_s": round(validate_seconds, 3),
              "commit_s": round(commit_seconds, 3), "initial_ui_interactive_s": round(interactive_seconds, 3),
              "page_switch_median_ms": round(statistics.median(timings), 2), "page_switch_max_ms": round(max(timings), 2),
              "thumbnail_files_on_open": thumbnails_on_open, "cache_budget_mb": 16, "evictions": evictions,
              "memory_samples": samples, "high_resolution": highres, "platform": sys.version,
              "qt_platform": os.environ.get("QT_QPA_PLATFORM", "windows"), "result": "PASS"}
    report_path = root / report_destination if report_destination else root / "docs" / "phase1_metrics.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="Optional separate report path; historical metrics preserved")
    main(parser.parse_args().report)
