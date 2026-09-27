"""Initial project database schema."""
VERSION = 6

DDL = """
CREATE TABLE projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, schema_version INTEGER NOT NULL,
 source_mode TEXT NOT NULL CHECK(source_mode IN ('copy','reference')),
 next_page_number INTEGER NOT NULL DEFAULT 1, batch_size INTEGER NOT NULL DEFAULT 100,
 reading_direction TEXT NOT NULL DEFAULT 'japanese', created_at TEXT NOT NULL
);
CREATE TABLE source_files (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 kind TEXT NOT NULL, original_path TEXT NOT NULL, stored_path TEXT,
 sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, page_count INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'available', metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE pages (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 page_uid TEXT NOT NULL, display_order INTEGER NOT NULL, source_file_id TEXT REFERENCES source_files(id),
 source_page_index INTEGER NOT NULL DEFAULT 0, label TEXT NOT NULL DEFAULT '',
 width INTEGER, height INTEGER, status TEXT NOT NULL DEFAULT 'pending',
 revision INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
 UNIQUE(project_id,page_uid), UNIQUE(project_id,display_order)
);
CREATE TABLE batches (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 batch_number INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
 UNIQUE(project_id,batch_number)
);
CREATE TABLE batch_pages (
 batch_id TEXT NOT NULL REFERENCES batches(id), page_id TEXT NOT NULL REFERENCES pages(id),
 position INTEGER NOT NULL, PRIMARY KEY(batch_id,page_id), UNIQUE(batch_id,position)
);
CREATE TABLE styles (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL,
 settings_json TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE text_style_presets (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 role TEXT NOT NULL, name TEXT NOT NULL, settings_json TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(project_id,role)
);
CREATE TABLE text_blocks (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id), text_uid TEXT NOT NULL UNIQUE,
 sequence INTEGER NOT NULL, reading_order INTEGER NOT NULL, bbox_json TEXT NOT NULL,
 polygon_json TEXT NOT NULL DEFAULT '[]', source_text TEXT NOT NULL DEFAULT '',
 source_language TEXT, ocr_confidence REAL, writing_mode TEXT, rotation REAL NOT NULL DEFAULT 0,
 region_type TEXT, review_status TEXT NOT NULL DEFAULT 'pending', style_id TEXT REFERENCES styles(id),
 erase_data_json TEXT NOT NULL DEFAULT '{}', mask_path TEXT, active INTEGER NOT NULL DEFAULT 1,
 erase_status TEXT NOT NULL DEFAULT 'none', typeset_status TEXT NOT NULL DEFAULT 'pending',
 text_style TEXT NOT NULL DEFAULT '{}',
 style_role TEXT NOT NULL DEFAULT 'speech', style_override_json TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 0, UNIQUE(page_id,sequence)
);
CREATE TABLE translations (
 id TEXT PRIMARY KEY, text_block_id TEXT NOT NULL REFERENCES text_blocks(id),
 language TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending', source TEXT NOT NULL DEFAULT 'manual',
 revision INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
 provider_profile_id TEXT, provider TEXT, model TEXT, prompt_version TEXT,
 created_at TEXT NOT NULL DEFAULT '', UNIQUE(text_block_id,language)
);
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
 batch_id TEXT REFERENCES batches(id), status TEXT NOT NULL DEFAULT 'pending',
 total_units INTEGER NOT NULL DEFAULT 0, completed_units INTEGER NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
 last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 options_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE task_items (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), page_id TEXT REFERENCES pages(id),
 status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT, started_at TEXT, finished_at TEXT,
 usage_json TEXT NOT NULL DEFAULT '{}', duration_ms INTEGER NOT NULL DEFAULT 0,
 UNIQUE(task_id,page_id)
);
CREATE TABLE history (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), command_type TEXT NOT NULL,
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, before_json TEXT NOT NULL,
 after_json TEXT NOT NULL, created_at TEXT NOT NULL, group_id TEXT,
 undone INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE document_exports (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 batch_id TEXT NOT NULL REFERENCES batches(id), protocol_version TEXT NOT NULL,
 export_revision INTEGER NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE document_imports (
 id TEXT PRIMARY KEY, document_export_id TEXT REFERENCES document_exports(id),
 path TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE ocr_runs (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id),
 engine TEXT NOT NULL, engine_version TEXT, model TEXT, model_version TEXT,
 parameters_json TEXT NOT NULL, raw_detection_json TEXT NOT NULL,
 raw_recognition_json TEXT NOT NULL, processing_ms INTEGER NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX idx_pages_order ON pages(project_id,display_order);
CREATE INDEX idx_task_items_status ON task_items(task_id,status);
CREATE INDEX idx_ocr_runs_page ON ocr_runs(page_id,created_at);
"""
from app.translation.schema import AI_DDL
DDL += AI_DDL
