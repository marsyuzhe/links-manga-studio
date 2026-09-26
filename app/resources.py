"""Find bundled resources in source trees and PyInstaller onedir builds."""
from pathlib import Path
import sys


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative
