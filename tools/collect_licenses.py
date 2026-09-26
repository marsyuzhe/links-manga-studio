"""Copy license texts from exact installed wheel versions into the portable folder."""
from __future__ import annotations

import importlib.metadata
import shutil
import sys
from pathlib import Path


def copy_distribution(name: str, destination: Path) -> None:
    distribution = importlib.metadata.distribution(name)
    root = Path(distribution.locate_file(""))
    files = distribution.files or []
    for file in files:
        relative = Path(str(file))
        if not any(part.lower() in ("licenses", "license", "notice") or part.lower().startswith("license")
                   or part.lower().startswith("notice") for part in relative.parts):
            continue
        source = root / relative
        if source.is_file():
            target = destination / name / relative
            if "pypdfium2" in name.lower() and "BUILD_LICENSES" in relative.parts:
                target = destination / name / "PDFium-ThirdParty" / relative.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def main(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    project = Path(__file__).resolve().parents[1]
    shutil.copytree(project / "licenses" / "Qt", destination / "Qt", dirs_exist_ok=True)
    shutil.copytree(project / "licenses" / "RapidOCR", destination / "RapidOCR", dirs_exist_ok=True)
    opencv_packages = []
    for candidate in ("opencv-python", "opencv-python-headless"):
        try:
            importlib.metadata.distribution(candidate)
            opencv_packages.append(candidate)
        except importlib.metadata.PackageNotFoundError:
            pass
    for package in ("pypdfium2", *opencv_packages, "Pillow", "python-docx", "fonttools",
                    "PySide6-Essentials", "shiboken6", "numpy", "shapely", "pyclipper",
                    "PyYAML", "lxml", "omegaconf", "requests", "rapidocr", "certifi",
                    "charset-normalizer", "idna", "urllib3", "antlr4-python3-runtime",
                    "colorlog", "flatbuffers", "protobuf", "six", "tqdm", "typing_extensions",
                    "packaging"):
        copy_distribution(package, destination)
    for name in ("LICENSE", "ThirdPartyNotices.txt"):
        source = Path(importlib.metadata.distribution("onnxruntime").locate_file("onnxruntime")) / name
        if source.is_file():
            target = destination / "onnxruntime" / name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
    (destination / "THIRD_PARTY.md").write_text("""# Third-party notices

The application uses Qt/PySide6 Essentials (LGPL-3.0/GPL/commercial options), PDFium via pypdfium2 (BSD-3-Clause/Apache-2.0 and PDFium dependency notices), RapidOCR engineering code (Apache-2.0), ONNX Runtime (MIT), OpenCV (Apache-2.0 plus wheel third-party notices), Pillow (MIT-CMU), python-docx (MIT), and fontTools (MIT). The three bundled OCR artifacts have been matched by SHA256 to RapidOCR's explicit Apache-2.0 model notice. Model ownership remains with Baidu and/or the applicable PaddleOCR rights holders; retain their conversion and attribution notices.

Qt libraries are separate files in `runtime/` and may be replaced with compatible modified versions. Qt for Python source and license information: https://doc.qt.io/qtforpython-6/ and https://code.qt.io/pyside/pyside-setup.git . PDFium notices are in `pypdfium2/PDFium-ThirdParty/`. The RapidOCR model names and upstream credits are in `RapidOCR/MODELS.txt`. This folder preserves the notices shipped by the installed wheel builds.
""", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
