# Architecture overview

Links Manga Studio is a local PySide6 desktop application. `app/main.py` starts the UI; `app/ui/` contains the startup window, workbench, canvas, panels and dialogs. Appearance tokens and mode persistence live in `app/themes/` and `app/config.py`.

Each `.lmw` project contains `project.json`, SQLite data and project-owned directories. `app/project.py` owns create/open/close, `app/database/` manages schema and migrations, and `app/pages/` keeps stable Page UIDs separate from display order. Source files can be copied into the project or referenced by path and hash.

`app/importers/` and `app/pdf/` register image/PDF pages. `app/ocr/` runs local OCR and persists raw output and TextBlocks. `app/documents/` and `app/word_protocol.py` exchange translations using stable Word field identifiers. `app/rendering/`, `app/styles/` and `app/quality/` handle non-destructive erase/refill, font/style inheritance, Auto Fit and read-only checks. `app/tasks/` tracks resumable work; `app/history.py` supports undo/redo.

Application PDF rendering uses pypdfium2 / PDFium. Synthetic tests use PDFium to create blank multi-page PDFs and the existing Qt QPdfWriter to draw original text panels; PyMuPDF is no longer a project dependency and remains excluded from the Windows build. Core edits are committed to SQLite promptly; cached previews and thumbnails are reproducible from sources. Translation is manual-first, OCR runs locally, and non-destructive TextBlocks retain their identity across erase/refill operations.

## AI translation (0.6.0)

`app/translation/` separates profiles and Windows credential storage, provider HTTP adapters, page context/validation/transactions, and persistent task execution. Providers implement manual, OpenAI-compatible, Ollama and local OpenAI-compatible protocols using Python standard-library HTTP. Local requests accept only loopback endpoints and bypass proxies; redirects are rejected. Reserved Gemini/Claude interfaces are not enabled.

Schema 5 adds `project_translation_settings`, `glossary`, `character_notes`, translation provenance fields, task `options_json`, and per-item usage/duration. Nonsecret profiles live in app settings; project data stores profile IDs, never credentials. Credential Manager uses Windows native APIs. Existing Page/Text IDs and DOCX protocol are unchanged. Migration backs up the database first.

Requests contain reading-order targets and optional adjacent-page context. Strict UID validation rejects invalid whole-page output. Snapshot comparison inside `BEGIN IMMEDIATE` rejects responses that would overwrite concurrent edits. Each page's translation changes form one Undo group. HTTP workers run with bounded concurrency; database commits remain serialized. Resumable task options contain only profile ID and overwrite/scope flags. Provider and project rules are resolved again on resume. Logs omit raw request/response bodies and credentials. See [AI guide](AI_TRANSLATION.md).

## 0.6.0 compact desktop UI

Four toolbar groups reuse existing QAction menus; the Translate primary click opens the in-app Translation Center with current-page scope; manual input remains in the Inspector. Inspector pages are scrollable to prevent laptop-height overflow; notes and advanced provider/project settings use flat disclosure sections. Provenance appears as one quiet state menu, with full details loaded only on demand. Task progress is signalled to a clickable status-bar indicator, leaving the bottom task/quality/log panels collapsed until requested. Neutral themes share the same layout/QSS. Existing importers, caches, database schema 5 and UID/DOCX protocols are retained. Version-separated build output preserves old onedir and ZIP files.


## UX/UI R2

MainWindow's existing QStackedWidget hosts the manga workspace, Translation Center and independent Glossary workspace. Translation Center reuses existing providers/credentials/TaskService and page transactions; it polls persistent metrics at 500ms, with native task/history/services tabs. Settings holds defaults only. Safe request records separate task-level Token from TextBlock translations. Missing/partial usage is explicit. New task options snapshot project parameters and model name; resume reads current endpoint/glossary and revalidates cloud consent. Pause stops dispatch and permits current work to commit; close waits for these writes and leaves the task paused.

Schema 6 additively extends glossary/category/modified time, character note and translation_requests, backed up by the existing migration mechanism. Glossary CRUD/CSV shares existing data and HistoryService; no new UID or OCR/import/cache architecture. Both themes add border_strong/focus_ring/selected_border tokens. OCR delegate draws clear selection and focus; native Windows frame remains unchanged.
