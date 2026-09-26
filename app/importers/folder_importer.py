"""Filesystem discovery and deterministic natural sorting."""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def natural_key(value: str | Path) -> tuple:
    text = str(value).replace("\\", "/").casefold()
    return tuple((1, int(part)) if part.isdigit() else (0, part)
                 for part in re.split(r"(\d+)", text))


@dataclass
class ScanResult:
    paths: list[Path] = field(default_factory=list)
    ignored: int = 0
    root: Path | None = None


def scan_files(paths: list[Path]) -> ScanResult:
    supported = [p.resolve() for p in paths if p.suffix.lower() in EXTENSIONS]
    return ScanResult(sorted(supported, key=lambda p: (natural_key(p), str(p))), len(paths) - len(supported))


def scan_folder(root: Path) -> ScanResult:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")
    paths: list[Path] = []
    def fail(error: OSError) -> None:
        raise error
    for parent, directories, filenames in os.walk(root, followlinks=False, onerror=fail):
        directories[:] = [d for d in directories if not Path(parent, d).is_symlink()]
        paths.extend(Path(parent, filename) for filename in filenames)
    result = scan_files(paths)
    result.root = root
    return result
