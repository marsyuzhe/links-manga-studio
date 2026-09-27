AI_DDL = """
CREATE TABLE project_translation_settings (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), provider_profile_id TEXT,
 settings_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE glossary (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 source_term TEXT NOT NULL, target_term TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
 case_sensitive INTEGER NOT NULL DEFAULT 0, exact_match INTEGER NOT NULL DEFAULT 1, category TEXT NOT NULL DEFAULT 'other', updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE character_notes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, translated_name TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', speech_style TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '');
CREATE TABLE translation_requests (
 id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), item_id TEXT NOT NULL REFERENCES task_items(id),
 page_id TEXT NOT NULL REFERENCES pages(id), provider TEXT NOT NULL, model TEXT NOT NULL,
 block_count INTEGER NOT NULL, request_count INTEGER NOT NULL, status TEXT NOT NULL,
 error_code TEXT, usage_json TEXT NOT NULL DEFAULT '{}', duration_ms INTEGER NOT NULL, created_at TEXT NOT NULL);
"""

# Historical migrations must not consume the evolving fresh-project schema.
AI_DDL_V5 = """
CREATE TABLE project_translation_settings (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), provider_profile_id TEXT,
 settings_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE glossary (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 source_term TEXT NOT NULL, target_term TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
 case_sensitive INTEGER NOT NULL DEFAULT 0, exact_match INTEGER NOT NULL DEFAULT 1);
CREATE TABLE character_notes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, translated_name TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', speech_style TEXT NOT NULL DEFAULT '');
"""
