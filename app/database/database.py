"""Configured SQLite connection."""
import sqlite3
from pathlib import Path
from .migrations import migrate


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if mode.lower() != "wal":
        connection.close()
        raise RuntimeError(f"Could not enable SQLite WAL: {mode}")
    migrate(connection, path)
    return connection
