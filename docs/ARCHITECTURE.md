# Architecture overview

Links Manga Studio is a local PySide6 desktop application. `app/main.py` starts the UI; `app/ui/` contains the startup window, workbench, canvas, panels and dialogs. Appearance tokens and mode persistence live in `app/themes/` and `app/config.py`.

Each `.lmw` project contains `project.json`, SQLite data and project-owned directories. `app/project.py` owns create/open/close, `app/database/` manages schema and migrations, and `app/pages/` keeps stable Page UIDs separate from display order. Source files can be copied into the project or referenced by path and hash.

`app/importers/` and `app/pdf/` register image/PDF pages. `app/ocr/` runs local OCR and persists raw output and TextBlocks. `app/documents/` and `app/word_protocol.py` exchange translations using stable Word field identifiers. `app/rendering/`, `app/styles/` and `app/quality/` handle non-destructive erase/refill, font/style inheritance, Auto Fit and read-only checks. `app/tasks/` tracks resumable work; `app/history.py` supports undo/redo.

Application PDF rendering uses pypdfium2 / PDFium. Synthetic tests use PDFium to create blank multi-page PDFs and the existing Qt QPdfWriter to draw original text panels; PyMuPDF is no longer a project dependency and remains excluded from the Windows build. Core edits are committed to SQLite promptly; cached previews and thumbnails are reproducible from sources. Translation is manual-first, OCR runs locally, and non-destructive TextBlocks retain their identity across erase/refill operations.
