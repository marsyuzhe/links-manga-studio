"""Simple local crash marker; never uploads diagnostics."""
from __future__ import annotations

import os
from pathlib import Path


class SessionGuard:
    def __init__(self, config_root: Path) -> None:
        self.path = config_root / "session.running"
        self.previous_unclean = self.path.exists()

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(str(os.getpid()), encoding="ascii")

    def close(self) -> None:
        self.path.unlink(missing_ok=True)
