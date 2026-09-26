"""Transactional schema migrations with a pre-migration SQLite backup."""
from pathlib import Path
import sqlite3
import uuid
from .schema import DDL, VERSION


def migrate(connection, path: Path) -> None:
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    if current > VERSION:
        raise RuntimeError(f"Project database version {current} is newer than app version {VERSION}")
    if current == 0:
        connection.executescript("BEGIN IMMEDIATE;" + DDL + f"PRAGMA user_version={VERSION}; COMMIT;")
        return
    if current < 2:
        backup_root = path.parent / "backups"
        backup_root.mkdir(exist_ok=True)
        backup_path = backup_root / f"before-schema-v2-{uuid.uuid4().hex[:8]}.sqlite3"
        backup = sqlite3.connect(backup_path)
        try:
            connection.backup(backup)
        finally:
            backup.close()
        with connection:
            connection.execute("ALTER TABLE history ADD COLUMN undone INTEGER NOT NULL DEFAULT 0")
            connection.execute("UPDATE projects SET schema_version=2")
            connection.execute("PRAGMA user_version=2")
        current = 2
    if current < 3:
        backup_root = path.parent / "backups"
        backup_root.mkdir(exist_ok=True)
        backup = sqlite3.connect(backup_root / f"before-schema-v3-{uuid.uuid4().hex[:8]}.sqlite3")
        try:
            connection.backup(backup)
        finally:
            backup.close()
        with connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(text_blocks)")}
            if "erase_status" not in columns:
                connection.execute("ALTER TABLE text_blocks ADD COLUMN erase_status TEXT NOT NULL DEFAULT 'none'")
            if "typeset_status" not in columns:
                connection.execute("ALTER TABLE text_blocks ADD COLUMN typeset_status TEXT NOT NULL DEFAULT 'pending'")
            if "text_style" not in columns:
                connection.execute("ALTER TABLE text_blocks ADD COLUMN text_style TEXT NOT NULL DEFAULT '{}'")
            connection.execute("UPDATE text_blocks SET erase_status='erased' WHERE erase_data_json NOT IN ('{}','')")
            connection.execute("UPDATE text_blocks SET typeset_status='ready' WHERE id IN (SELECT text_block_id FROM translations WHERE trim(text)<>'')")
            connection.execute("UPDATE text_blocks SET text_style=(SELECT settings_json FROM styles WHERE id=text_blocks.style_id) WHERE style_id IS NOT NULL")
            connection.execute("UPDATE projects SET schema_version=3")
            connection.execute("PRAGMA user_version=3")
        current = 3
    if current < 4:
        backup_root = path.parent / "backups"
        backup_root.mkdir(exist_ok=True)
        backup = sqlite3.connect(backup_root / f"before-schema-v4-{uuid.uuid4().hex[:8]}.sqlite3")
        try:
            connection.backup(backup)
        finally:
            backup.close()
        with connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(text_blocks)")}
            if "style_role" not in columns:
                connection.execute("ALTER TABLE text_blocks ADD COLUMN style_role TEXT NOT NULL DEFAULT 'speech'")
            if "style_override_json" not in columns:
                connection.execute("ALTER TABLE text_blocks ADD COLUMN style_override_json TEXT NOT NULL DEFAULT '{}'")
            connection.execute("""CREATE TABLE IF NOT EXISTS text_style_presets (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                role TEXT NOT NULL, name TEXT NOT NULL, settings_json TEXT NOT NULL DEFAULT '{}',
                revision INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(project_id,role))""")
            connection.execute("UPDATE projects SET schema_version=4")
            connection.execute("PRAGMA user_version=4")
