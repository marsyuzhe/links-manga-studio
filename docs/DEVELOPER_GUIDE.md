# Developer guide — Links Manga Studio 0.6.0

This is the working guide. Architecture rationale belongs in [ARCHITECTURE.md](ARCHITECTURE.md). Product names differ from the preserved Python package/EXE/config identifiers for compatibility.

## Setup

Use Windows x64 and Python 3.12 for the tested build; source metadata supports Python 3.11+.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[imaging,test]"
.\.venv\Scripts\python.exe -m app.main
```

Runtime: PySide6-Essentials, PDFium, RapidOCR/ONNX Runtime, python-docx, fontTools; image operations need OpenCV/NumPy. The imaging extra installs headless OpenCV. RapidOCR may bring OpenCV transitively; use the pinned Windows build environment for packaging, avoid manually installing competing cv2 wheels. Test extras are pytest/pytest-qt. PyInstaller and pinned transitive dependencies live in requirements-build-win-py312.txt. Provider HTTP uses stdlib; no LLM runtime is required.

## Find the code

| Area | Main files |
|---|---|
| Startup, preferences, logs | app/main.py, config.py, logging_setup.py, diagnostics.py |
| Project ownership | app/project.py, app/database/database.py, schema.py, migrations.py |
| Import/page/cache | app/importers/, app/pdf/, app/pages/, app/cache/ |
| OCR and review | app/ocr/pipeline.py (including ModelManager/RapidBackend), review.py |
| Translation profiles/protocol/commit | app/translation/profiles.py, providers.py, service.py, tasks.py |
| Word exchange | app/documents/word.py, app/word_protocol.py |
| Rendering/fonts/layout | app/rendering/, app/styles/ |
| Undo/task recovery | app/history.py, app/tasks/service.py, app/session.py |
| Native UI/lifecycle | app/ui/window.py, workspace.py, workers.py, translation_center.py, glossary_workspace.py |
| Packaging/audit | tools/build_release.ps1, collect_licenses.py, audit_release.py, audit_public_tree.py |

## Projects, identity and migrations

A .lmw is a folder containing project.json, project.sqlite3 and sources/derived/cache/export/backup/log subfolders. Reference sources remain external; Copy sources are owned by the project.

SQLite enables foreign_keys, WAL and busy_timeout. Core edits use transactions; UI autosave is not a substitute. Current schema is **6**. Historical migrations use fixed versioned DDL and make backups; never rewrite historical DDL using the current schema.

Internal row IDs, permanent Page UID, display_order and source_page_index have distinct roles. Text UID must survive matched OCR, cleaning, translation and Word exchange. Never derive an existing UID from list position or translated headings. Do not open a migrated project for writing with an older app; restore a complete older backup.

## OCR and Word

OCRPipeline persists engine/model/version/parameters/raw output before postprocessing. Matching preserves identities where boxes correspond; inspect association tests before changing matching thresholds. TextBlockService owns source/review edits.

WordExchange maps stable internal protocol identifiers and Text UID; display headings are localizable. Validate duplicate/unknown IDs and preview before applying. Preserve both protocol constants and compatibility tests.

## Translation and secrets

ProfileStore owns non-secret settings; WindowsSecrets owns Credential Manager data. Provider objects are created for explicit user operations. Startup/project open must not request credentials, contact services, scan models or launch a local server.

Provider output validates the exact requested UID set before any write. Context pages and glossary help the request but are not writable target blocks. TranslationService checks original snapshots before committing; protected manual/reviewed edits remain protected. Unknown usage stays unknown. Never log raw service exceptions, response text or keys.

Translation tasks store safe configuration/profile IDs, not clients or credentials. Worker HTTP futures communicate through queues; SQLite commits stay on the owning task thread/connection. Pause prevents new requests while in-flight work can finish; cancellation/resume use durable states.

## Rendering, cache and fonts

PageRenderer composes derived cleaning and translated layers without modifying original sources. Layout uses bounded font search and explicit overflow. PDF coordinates use the existing 72-DPI convention; render only requested pages.

ImageCache owns decoded QImage memory, independently of pixmap/thumbnails/disk assets. An oversized image bypasses retention; don't silently turn the budget into a minimum. Installed font metadata uses a file fingerprint cache, scanning on explicit font/quality tools. Fonts require separate licensing.

## Undo, workers and UI

HistoryService captures supported mutations within the edit transaction. Add meaningful Undo assertions when adding mutation logic. TaskService marks interrupted work for recovery; completed items are not replayed as new work.

Job owns a worker until join/disposal; signal callbacks update UI on its thread. MainWindow joins work before closing project state. Async canvas results validate the active request/page before display.

Secondary Translation Center/Glossary widgets are cached on first navigation; passive project/theme/language operations must not create them. Hidden Translation Center polling stops. History uses a 100-row window with explicit older-record loading. Preserve scope previews and dialog inset/focus geometry.

## Tests and audit

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_full_workflow.py
.\.venv\Scripts\python.exe -m pytest tests/test_full_workflow.py -q
.\.venv\Scripts\python.exe -m compileall -q app tests tools
.\.venv\Scripts\python.exe -m tools.audit_code_hygiene
.\.venv\Scripts\python.exe -m tools.audit_public_tree
.\.venv\Scripts\python.exe -m tools.benchmark_phase1 --report dev_data/local-performance.json
```

The separate full-workflow test builds/exports 1,000 synthetic PDF pages and is expensive. The image benchmark covers import/navigation/cache, not the same PDF end-to-end flow. Real OCR is exercised by runtime tests; providers use mocks/loopback HTTP. Do not mark actual APIs, local models, visible UX or physical DPI as tested based on these.

## Build and validate

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-win-py312.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_release.ps1
.\.venv\Scripts\python.exe -m tools.audit_release dist/Links-Manga-Studio-0.6.0-windows-x64.zip
```

Build is onedir under dist/0.6.0-final/. Retain older RCs. Runtime includes only required assets, core OCR models, user docs and license texts, not screenshots/developer data. Build scripts preserve an existing final ZIP in dist/history before replacement. Pinning does not guarantee bit-identical builds.

Extract the resulting ZIP to a fresh test directory; run EXE --smoke-test --smoke-output with offscreen and isolated LMW_CONFIG_DIR, check exit/result JSON, then perform visible acceptance separately. Public source staging is local and excludes binaries/weights/private projects. Never commit keys or personal logs.

## Scope for changes

Feature freeze applies to this release. Fix concrete bugs with small patches and affected regression; preserve schema, UID, Word protocol, protected edits and worker ownership. Compatibility/deprecation comments name the reason and earliest removal boundary. No generic TODOs or empty comments as documentation targets.
