# Changelog

## 0.6.0 UX/UI R2

- Independent native Translation Center task/history/services and project Glossary workspace.
- Protected preflight, request/block progress, missing/partial Token coverage, single failure retry and review.
- Pause permits current requests to commit; quit persists paused tasks; cancellation retains results.
- Glossary categories/search/CSV/conflicts and character master/detail, immediate saves and existing Undo.
- Strong selection/focus/hover/pressed states, panel borders, 7px splitters and safe insets in both themes.
- Schema 6 additive migration with backups; product version and UIDs unchanged.
- Real visible UX requires user acceptance. No GitHub publishing.

## 0.6.0 — AI Translation and compact UI

- Optional OpenAI-compatible cloud, Ollama and local OpenAI-compatible translation; manual remains available.
- Windows Credential Manager profiles, first-use cloud consent, glossary/context and versioned prompts.
- UID-validated page tasks with pause/resume/retry, review protections, per-page Undo and provenance.
- Schema 5 migration, bilingual UI, DOCX compatibility and AI draft quality warning.
- Four workflow toolbar groups, scrollable compact Inspector, collapsed advanced settings and status-bar task progress.
- Existing 0.5.0 portable artifact is preserved; new build uses a version-separated directory.


Changes use a Keep a Changelog style. v0.5.0 is the initial public-release candidate; publication itself is performed by the owner.

## [0.5.0] - 2026-09-26

### Added

- Local OCR, PDF/image projects, stable batches and DOCX translation exchange.
- Non-destructive erase/refill, project font roles, Auto Fit and Quality Check.
- Dark/Light/System appearance and Chinese/English interface.
- Apache-2.0 LICENSE/NOTICE, model provenance, community files and manual publishing guide.

### Changed

- Public product branding is Links Manga Studio, created by Links Tam.
- Synthetic PDF fixtures use PDFium and Qt; removed test-only PyMuPDF dependency.

### Fixed

- Release packaging no longer includes theme bytecode with development paths.
- Test fixture import layout preserves existing test helper imports.
