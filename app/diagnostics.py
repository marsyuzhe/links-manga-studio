"""Local environment diagnostics without external calls."""
from __future__ import annotations

import platform
import sqlite3
import sys
import importlib.metadata
from pathlib import Path

from . import __version__


def _version(module_name: str, attribute: str = "__version__") -> str:
    try:
        module = __import__(module_name)
        return str(getattr(module, attribute, "unknown"))
    except ImportError:
        return "not installed"


def collect(project_path: Path | None, log_path: Path) -> dict[str, str]:
    try:
        from app.ocr.pipeline import ModelManager
        model = ModelManager().status()
    except Exception:
        model = {"engine": "Unavailable", "model": "Unavailable", "installed": False,
                 "device": "CPU", "path": "Unavailable"}
    try:
        import onnxruntime
        cuda = "CUDAExecutionProvider" in onnxruntime.get_available_providers()
    except ImportError:
        cuda = False
    return {
        "App Version": __version__, "Build Version": __version__, "Python Version": sys.version.split()[0],
        "Windows Version": platform.platform(), "PySide6 Version": _version("PySide6"),
        "SQLite Version": sqlite3.sqlite_version, "OpenCV Version": _version("cv2"),
        "PDFium Version": importlib.metadata.version("pypdfium2"),
        "PyMuPDF Version": _version("pymupdf", "VersionBind"),
        "OCR Runtime": "ONNX Runtime " + (importlib.metadata.version("onnxruntime") if model["installed"] else "unavailable"),
        "OCR Engine": model["engine"] + " " + (importlib.metadata.version("rapidocr") if model["installed"] else ""),
        "OCR Model": model["model"], "OCR Model Installed": str(model["installed"]),
        "OCR Model Path": model["path"], "Device": model["device"],
        "CUDA Available": str(cuda), "GPU": "Not selected" if not cuda else "CUDA device available",
        "Project Path": str(project_path) if project_path else "No project open",
        "Cache Path": str(project_path / "cache") if project_path else "No project open",
        "Log Path": str(log_path),
    }
