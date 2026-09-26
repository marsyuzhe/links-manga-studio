# Internal Development History — Development status

This is a historical development log, not the current release manifest. Earlier v0.5.0 ZIP hashes and “final” packaging statements below are **superseded / historical**. The sole current candidate hash is in PUBLICATION_AUDIT.md. No GitHub publication was performed by this task.

## GitHub initial public release preparation (2026-09-25)

- Public author identity is Links Tam only; About/Startup/screenshots and EXE metadata have been checked. README (English/Chinese), community templates, CI, release notes, architecture, dependency/model/license audits and synthetic fixtures are prepared.
- Fresh Python 3.12 source environment: 15 smoke checks and **80 core tests passed, 0 failed**. Final Windows ZIP: fresh first start returned 0 with empty Recent Projects; 15 packaged smoke checks passed. Source and ZIP privacy audits found 0 actionable issues. See `docs/PUBLICATION_AUDIT.md` for evidence and the final ZIP hash.
- **Blocked for public publishing by owner decisions:** main project LICENSE, specific OCR weight redistribution rights, dedicated Git repository root/name/visibility (current Git root is an unrelated parent with 0 commits), private vulnerability reporting/conduct contact, and real Windows UI acceptance. No push/tag/public repository was created.
- Next action after owner decisions: add LICENSE, resolve model packaging if necessary, re-run core tests/build/audits if affected, then follow `docs/GITHUB_RELEASE_CHECKLIST.md` to stage only this project and publish the approved ZIP/hash.

## 0.5.0 release (2026-09-25)

Cross-version check: the preserved **0.4.1 portable EXE** generated a genuine old-schema project. A copy opened in 0.5.0 with Page UID `P0001`, Text UID `P0001-T001`, a translation fixture and byte-identical `project.json` retained. The translation row was inserted into the copied 0.4.1 database to exercise the persisted Word/translation table shape; the original project was untouched.

**Release complete on 2026-09-25.** Final short regression: **79 passed, 0 failed** in 16.28 s. The one font-metric fixture adjusted during full regression passed again separately; the unchanged thousand-page end-to-end test had passed before this work and was excluded from the final short run. A copied genuine schema-v2 project with one page, one OCR TextBlock and one translation migrated to schema v4 with all three records preserved. Source and freshly extracted packaged EXE smoke: **15 checks passed**, including real RapidOCR inference. Final ZIP: `dist/Links-Manga-Studio-0.5.0-windows-x64.zip` (159,241,097 bytes). SHA256: `39E7D8BE8EAB8D2AAED0D29FBEDF7B4D5B9EDC3FC7A6D27BD55B9CDCBAD3EF7C`; companion `.sha256` file exists. EXE Windows metadata shows ProductName `Links Manga Studio`, FileVersion `0.5.0`. Offscreen snapshots refreshed in `docs/ui_snapshots/0.5.0/`; visual QA found and fixed drop-zone label background bands and duplicated recent-project thumbnails. Real visible Windows UI remains **NOT TESTED** by user instruction; see `docs/USER_ACCEPTANCE_0.5.0.md`.

- Branding/author, Dark/Light/System token themes, runtime theme persistence, About, startup/recent project improvements and workspace theme-aware custom painting are implemented. `app/__init__.py` and `pyproject.toml` are 0.5.0; old config path, project format, SQLite schema, UIDs and Word protocol remain.
- Simple mode Auto Fit feedback and quality issue location were added. Affected UI/workflow/i18n tests: **20 passed**. In Simple mode the issue list uses a readable block number; Advanced mode shows the stable Text UID.
- Release metadata, the ZIP filename, acceptance guide, final screenshots, PyInstaller build, fresh extraction smoke and SHA256 are complete.
- Real visible Windows UI acceptance remains **NOT TESTED** by explicit user instruction; user will perform it.

Updated: 2026-09-25. Continue from this file and the current working tree. Do not reinitialize the repository.

## 0.4.0 current work

0.4.1 visual redesign adds theme tokens/QSS, SVG icon system, reusable button/section/empty-state components, centered startup, one-row workflow toolbar, left tool rail, compact delegated page rows, inspector hierarchy, bottom quality panel and Settings navigator. Existing services/schema remain unchanged. Final regression: 77 short tests passed and the 1000-page end-to-end test passed in 76.98 seconds. Qt offscreen snapshots are in `docs/ui_snapshots`; `QT_QPA_FONTDIR=C:/Windows/Fonts` is needed for readable Windows offscreen text. Real visible UI acceptance remains user-led per `docs/UI_ACCEPTANCE_0.4.md`.

0.4.1 Windows x64 onedir and ZIP built on 2026-09-25. A fresh ZIP extraction passed 13 release smoke checks, including real RapidOCR inference; packaged dark QSS and acceptance guide were checked. ZIP SHA256: `4BF6712D1F5A226BC55DECE7827382561B9BC548B20F483F282CEC2E3FAA5980`. Real visible-window validation remains NOT TESTED by instruction.

Schema v4 adds project text-style presets and per-block role/override fields with migration backup. Project style inheritance, grouped undo/redo, Windows font metadata cache/browser/favorites/recent, qualitative font matching, Auto Fit 2.0, Chinese punctuation wrapping, basic vertical layout, read-only quality checks and navigation, and a revised inspector are implemented. Translation edits use a short debounce and flush on selection change. 72 short tests and the 1000-page integrated test passed on 2026-09-25. Source/packaged smoke and release ZIP status are recorded in the final release report. Real visible Windows UI validation is user-led; see `docs/UX_ACCEPTANCE_0.4.md`.

## Complete

- Phase 0 project, SQLite schema, migrations, diagnostics and startup window.
- Phase 1 image import, pages, thumbnails, canvas, Copy/Reference sources, source relocation.
- Phase 1 thousand-page image benchmark: `docs/phase1_metrics.json` (1000 pages, 11.225 s preflight, 1.19 s commit, 0.217 s first interaction, 9.71 ms sampled page switch median, cache bounded at 16 MB).
- UI polish: runtime zh_CN/en_US switching and persistent language, multi-resolution Windows ICO and packaged resource lookup.
- Regression suite after fixing an invalid pytest-qt callback: 26 passed (Qt offscreen, 2026-09-22).
- Phase 2 PDF metadata import and lazy PDF rendering with separate preview/OCR/thumbnail disk cache. Generated 1000-page PDF test covers Copy/Reference, no eager rasterization, distinct DPI cache keys, source loss and duplicate prevention. Windows path-length cache bug found and fixed.
- Persistent per-page task state foundation with pause, interruption recovery, retry, failure isolation and resume.
- PDF workspace offscreen navigation/race test passes. Local RapidOCR CPU engine is installed with package ONNX models; real inference and project OCR task tests pass. Raw OCR runs and TextBlocks are written in a transaction; reOCR uses region overlap to preserve matched Text UIDs.
- Explicit batch membership service: default 100-page batches produce 10 batches for 1000 pages and remain stable after page display-order edits. Full suite: 36 passed in 12.88 s (Qt offscreen, 2026-09-22).
- OCR canvas overlays and inspector review/manual translation editor. Edits commit immediately to SQLite. DOCX Light/Standard/Full export uses stable field bookmarks and project/batch/revision metadata; import reports matched/imported/empty/unknown/duplicate/conflict/missing and ignores table row order. Full suite: 40 passed in 15.29 s (Qt offscreen, 2026-09-22).
- Shared edited-page renderer is used for canvas and final export. Fill/inpaint, external masks, text fitting/Chinese punctuation wrapping and resumable PNG/JPEG/WEBP export are implemented. Qt mask brush/erase editor, manual SQLite/project/mask backup, crash marker and expanded OCR/CUDA diagnostics are implemented. Full suite: 46 passed in 17.59 s (Qt offscreen, 2026-09-22).
- PDF adapter switched from PyMuPDF to PDFium for redistributable licensing; all 46 existing tests passed after the switch. Schema v2 adds undo state with automatic SQLite backup and `project.json` version sync. TextBlock geometry/style/erase/translation/mask undo/redo and cached Windows font indexing now pass; full suite 51 passed in 17.93 s.
- Integrated 1000-page PDF import → 10 batches → simulated OCR blocks → DOCX exchange → mapped translations → 1000 PNG exports passed in 119.28 s. Real ONNX OCR sample is covered separately. README, release notes and manual acceptance guide added.
- Windows x64 PyInstaller onedir release and portable ZIP 0.1.0 built. Initial build exposed relative resource paths and a Poppler ICU DLL accidentally found on the host PATH; both packaging issues were fixed. Final EXE and newly extracted ZIP copy each passed noninteractive smoke: icon, zh_CN/en_US, project create/reopen, SQLite foreign keys/WAL, image loading, PDFium, Word/renderer imports and real RapidOCR CPU inference. SHA256 file generated. Final regression: 51 passed, 1 deselected (the previously passed 119-second 1000-page integrated test), 0 failed.
- Workflow UI refactor: PDF/image/folder drops, PDF direct-open project creation, visible workflow toolbar, left Pages/Batches/OCR/Project tabs, right Properties/Original/Translation/Erase/Typeset tabs, bottom Tasks/Logs/Export tabs, source-text TSV export, quick erase and on-canvas translation tool. Schema v3 adds erase_status, typeset_status and text_style with pre-migration backup. The existing translations table remains the canonical translation store, and stable Page/Text UIDs are unchanged. Five requested workflow tests plus v2 migration test added. Regression: 57 passed, 1 previously validated long integration test deselected, 0 failed. Windows 0.2.0 onedir/ZIP release rebuilt after UI styling; EXE from freshly extracted ZIP passed noninteractive icon, locale, SQLite/project, image, PDFium, Word/renderer and real RapidOCR inference smoke. SHA256 file generated. Old 0.1.0 ZIP remains as historical release and cannot open schema v3 projects.

## Current phase

Workflow UI refactor implemented and packaged as 0.2.0; awaiting user-led visible UI acceptance.

## Remaining release work

User-led visible Windows UI acceptance. A durable task configuration/retry audit remains for future development.

## Current bugs and limitations

- No known failing automated test. OCR currently uses packaged RapidOCR Chinese/English oriented models; Japanese manga accuracy and model selection need further work. DOCX document changes that remove bookmarks are reported as missing instead of guessed.
- PDFium wheel dependency notices are included in the release. PyMuPDF remains a test-only dependency for generating synthetic PDFs and is excluded from the portable application.
- Real visible GUI testing from this point is user-led by instruction; use terminal, pytest and Qt offscreen only.

## Next action

Wait for user-led visual acceptance feedback on 0.2.0. Do not start another phase without a new instruction.

## 2026-09-26 Apache release preparation

Earlier PyMuPDF and unresolved licensing notes are historical. Current project is Apache-2.0, PDF fixtures use PDFium/Qt, and OCR artifact hashes are covered by the preserved upstream notice. No GitHub public actions were performed.
