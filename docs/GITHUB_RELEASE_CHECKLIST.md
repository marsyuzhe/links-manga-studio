# GitHub publishing checklist — v0.5.0

Suggested repository name: `links-manga-studio`. Suggested description: “Local-first manga OCR, translation, cleaning and typesetting workspace for Windows.” Choose the actual GitHub owner and visibility yourself. Suggested topics: `manga`, `translation`, `ocr`, `typesetting`, `localization`, `pyside6`, `python`, `windows`, `rapidocr`.

Release tag: `v0.5.0`  
Release title: **Links Manga Studio v0.5.0 — Initial Public Release**  
Assets: Windows portable ZIP and its SHA256 file; GitHub may generate source archives.

GitHub: **NOT PUBLISHED**. Remote: **NOT CONFIGURED / USER CONTROLLED**. Release: **NOT CREATED**. All public actions belong to Links Tam. Follow [MANUAL_GITHUB_PUBLISH.md](MANUAL_GITHUB_PUBLISH.md).

## Before Push

- [x] **Apache-2.0 confirmed and added.** Complete LICENSE and NOTICE; test-only PyMuPDF removed.
- [x] **OCR Model Redistribution PASS.** Three exact hashes match upstream artifact-specific Apache-2.0 notice; preserved in licenses/RapidOCR.
- [ ] **Dedicated repository boundary confirmed.** The current Git root is the parent folder containing unrelated files. Do not publish its whole tree. Choose repository owner, name and visibility.
- [ ] Enable GitHub Private Vulnerability Reporting; configure a private community conduct contact.
- [ ] Review the staged files and Git history for secrets, personal data and copyrighted content before initial push.
- [ ] Perform the real Windows UI checks in [USER_ACCEPTANCE_0.5.0.md](USER_ACCEPTANCE_0.5.0.md); automated offscreen checks do not replace them.

## Prepared locally / Before Release

- [x] Public author display uses only Links Tam.
- [x] README (English/Chinese), architecture, contribution and security documents are prepared.
- [x] Third-party inventory, model review and synthetic asset provenance are documented.
- [x] `.gitignore` excludes project data, models, fonts, caches and builds.
- [x] Bug/feature templates, PR template and Windows CI workflow are prepared.
- [x] Release notes and synthetic UI screenshots are prepared.
- [x] Core tests and PyInstaller package re-run after final public-author/notices changes: 80 passed, 0 failed.
- [x] Fresh ZIP extraction, independent first-start/smoke and SHA256 verification after final build: 15 checks passed; Recent Projects empty.
- [x] Source and ZIP inspected for personal paths, secrets, logs, config, user projects and copyrighted media; both automated audits passed.
- [ ] Tag `v0.5.0` created **after** decisions and verification.
- [ ] GitHub Release created and assets uploaded **by the owner after confirmation**.

Source is Apache-2.0 and model terms are confirmed. Remaining user-run gates concern repository isolation, visible acceptance, security contact and remote CI. All public actions remain owner-controlled.

- [ ] GitHub Actions passes on both Python versions after your push (not executed on GitHub locally).
- [ ] Review English and Chinese release notes; update pending status after resolving licenses.
- [ ] Choose pre-release status and upload ZIP plus SHA256 yourself.

## After Release

- [ ] Check README, screenshots, topics, Issues and license without logging in.
- [ ] Download ZIP and SHA256, verify the checksum and launch from a fresh directory.
- [ ] Confirm Recent Projects is empty and run visible Windows acceptance.
- [ ] Retain final commit/tag, release URL and versioned artifacts.
