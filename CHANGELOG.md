# Changelog

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
