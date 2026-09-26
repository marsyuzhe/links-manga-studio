<p align="center"><img src="assets/icons/app_icon_128.png" width="96" alt="Links Manga Studio icon"></p>

# Links Manga Studio

[English](README.md) | [简体中文](README.zh-CN.md)

Local-first manga OCR, translation, cleaning and typesetting studio for Windows.

Created by **Links Tam**.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue) ![Python: 3.11–3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

**v0.5.0 — Initial Public Release candidate.** GitHub publication is performed by the owner; no fake CI or published-release badge is shown.

Local-first, manual-first and non-destructive: the built-in workflow processes pages locally without automatically uploading manga. No telemetry by default. Images and text remain in your `.lmw` project; no cloud account or translation API is required.

**Contents:** [Screenshots](#screenshots) · [Features](#features) · [Quick start](#quick-start) · [Workflow](#workflow) · [Fonts](#fonts) · [Performance](#large-project-benchmark) · [Development](#development) · [Limitations](#known-limitations) · [License](#license-and-credits)

## Screenshots

### Dark theme

![Dark startup — synthetic content](docs/images/startup-dark.png)
![Dark workspace — synthetic content](docs/images/workspace-dark.png)

### Light theme

![Light workspace — synthetic content](docs/images/workspace-light.png)

All screenshots use original synthetic demo content, not commercial manga. [Font browser](docs/ui_snapshots/0.5.0/font_browser.png) · [Quality Check](docs/ui_snapshots/0.5.0/quality_check.png)

## Features

### Import & projects

- PDF, images and folders; drag and drop, including direct PDF project creation.
- Large-project lazy thumbnails, bounded image cache and batch organization.
- Copy sources into a project or reference original paths with missing-source reporting.

### OCR

- Local RapidOCR CPU inference with bundled ONNX models.
- OCR review, confidence information, stable Text UIDs and persisted raw results.

### Translation

- Manual translation in persistent text blocks.
- DOCX export/import with stable internal field mapping rather than display headings.

### Cleaning & typesetting

- Erase, masks and Erase & Refill without deleting the TextBlock.
- Project fonts, style roles, per-block overrides and Auto Fit.
- Chinese punctuation-aware wrapping and editable layout.

### Quality & workflow

- Named Undo/Redo and Quality Check for missing translations or overflow.
- Dark, Light and System themes; Simplified Chinese and English UI.
- PNG/JPEG/WEBP export without an application or author watermark.

## Quick start

**Requirements:** Windows 10/11 x64. Portable users do not need Python. Download the latest Windows portable build from the GitHub Releases page once the owner publishes it; no repository URL is assumed here.

1. Download the ZIP and its `.sha256` file; verify the checksum.
2. Extract the entire ZIP. Keep `runtime/` beside `LinksMangaWorkspace.exe`.
3. Run the EXE. Its legacy filename preserves compatibility; the product is Links Manga Studio.
4. Drop a PDF, image or image folder into the startup window.
5. Run OCR and review the original text.
6. Enter translations locally or exchange DOCX batches.
7. Use Erase & Refill, then Quality Check.
8. Export finished pages.

Copy Into Project keeps sources inside `.lmw`; Reference Original Files records paths and hashes. Back up your project and external referenced files.

## Workflow

Import → OCR → Translate → Erase & Refill → Quality Check → Export

Erase retains the same Text UID, translation and styles. The project uses SQLite and immediate transactions for core edits. See [Architecture](docs/ARCHITECTURE.md).

## Fonts

Project Font Styles define reusable roles; Similar Font Recommendation offers visual matches. Rasterized manga generally does not preserve exact source font metadata, so this is visual recommendation, not exact font recovery. User-installed fonts are not redistributed with this project.

## Large project benchmark

An **internal synthetic 1,000-page image benchmark** previously measured preflight around 11.225 s, database commit 1.19 s, initial interactive UI 0.217 s and sampled page-switch median 9.71 ms. A 16 MB cache stress test remained bounded. These are historical measurements, not universal promises; hardware, source resolution and environment affect results. The heavy benchmark was not repeated for documentation changes.

## Development

Python 3.11 or 3.12 on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test,imaging]"
.\.venv\Scripts\python.exe -m app.main
```

### Tests

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_full_workflow.py
```

The excluded end-to-end test generates/exports 1,000 synthetic pages; run it when relevant. PDF tests use existing PDFium/Qt; PyMuPDF is not required. CI runs the core Windows suite without repository secrets; actual GitHub CI status is only known after a push.

### Windows build

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-win-py312.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_release.ps1
```

The observed build versions are pinned; bit-for-bit reproducibility is not promised. The onedir ZIP contains LICENSE, NOTICE and third-party licenses. `dist/` and model files are excluded from source Git; distribute binaries as Release assets. See [Contributing](CONTRIBUTING.md), [Security](SECURITY.md) and [manual publishing](docs/MANUAL_GITHUB_PUBLISH.md).

## Known limitations

- Windows-first; macOS/Linux have not been validated.
- Japanese OCR accuracy depends on the model and page quality; review results.
- Complex backgrounds may need manual erase/mask correction.
- Vertical typesetting is evolving; exact source fonts cannot be recovered reliably.
- Real visible Windows UI acceptance is recommended for each release.
- System theme is read at startup/selection; live Windows theme monitoring is not guaranteed.
- The portable executable is unsigned.

The software provides no manga content. Users are responsible for permission to process and distribute their material. See [Roadmap](ROADMAP.md) and [Changelog](CHANGELOG.md); no delivery dates are promised.

## License and credits

Links Manga Studio is licensed under the **Apache License 2.0**. You may use, copy, modify, redistribute, create derivative works and use commercially subject to its terms. This license does not require every fork or modification to be publicly released.

See [LICENSE](LICENSE) and [NOTICE](NOTICE). Third-party components and OCR models retain their own ownership and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [MODEL_LICENSES.md](MODEL_LICENSES.md). Credits include Qt/PySide6, PDFium, RapidOCR/PaddleOCR, ONNX Runtime, OpenCV, Pillow, python-docx, NumPy and fontTools. Contributors retain rights in their contributions.
