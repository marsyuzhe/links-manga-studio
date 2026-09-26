# v0.5.0 final local publication audit

Date: 2026-09-26. **READY FOR MANUAL GITHUB PUBLISH** means local materials are ready. GitHub **NOT PUBLISHED**; Remote **NOT CONFIGURED / USER CONTROLLED**; Release **NOT CREATED**. All public actions belong to Links Tam.

## Identity, source and assets

- Public product name: Links Manga Studio; version 0.5.0; author Links Tam. No real-name match in app, public docs, templates or release notes.
- Main source, documentation and original icon/synthetic assets: Apache-2.0, owner authorized. LICENSE is the unmodified complete official Apache text; NOTICE keeps separate upstream attribution.
- Sensitive Data Scan **PASS**, 0 actionable findings. Source scanner checks personal paths/emails/phone numbers, credential literals, tokens, bearer strings, private keys/private IPv4 and forbidden project/media artifacts. It is an automated review, not proof that every possible secret encoding is detectable.
- Git source candidates: **175 nonignored application files**; tracked application files: **0**. Forbidden project/cache/model/font/binary candidate names: 0. Current Git root remains the unrelated parent repository; it was not staged, initialized again or published. History commits: **0**, remotes: **0**; **History Scan PASS**. Follow MANUAL_GITHUB_PUBLISH.md to copy audited files into a separate directory.
- Source media are original generated icons, synthetic UI screenshots and code-drawn GitHub preview. No commercial manga, PDF, user project, font or model weight is included in source candidates. Provenance: ASSET_AUDIT.md and assets/README.md.

## License and exact OCR artifacts

- Test-only PyMuPDF removed from pyproject and build requirements, and uninstalled from the project environment. Application PDF rendering remains PDFium. Existing PDF tests now create fixtures through PDFium/Qt QPdfWriter.
- All three actual ZIP OCR artifact hashes match the explicit RapidOCR upstream model notice; Apache-2.0 redistribution confirmed. Full evidence is preserved at licenses/RapidOCR/UPSTREAM_MODEL_LICENSES.md (retrieved 2026-09-26, snapshot SHA256 `c5fd0e8603d3df743355b546121e6fe0f4ef8ff455c5a85c1681fd3ae520e153`). MODEL_LICENSES.md records filenames, versions, sources, download URLs, conversion attribution and conditions.
- Third-party runtime and development tables are separate. The new ZIP contains root LICENSE/NOTICE and collected vendor notices, including model evidence. Project Apache-2.0 does not replace vendor licenses.

## Tests and packaged acceptance

- Affected PDF/fixture tests: **5 PASS, 0 FAIL**.
- Final core suite after PyMuPDF removal: **80 total, 80 PASS, 0 FAIL, 0 SKIP**, 15.20 s. The separate heavy 1,000-page end-to-end test was not repeated. Previously measured performance is explicitly historical in README.
- Final Windows PyInstaller build succeeded using Python 3.12.14. PyMuPDF is absent from both environment and extracted package; defensive fitz/pymupdf exclusions remain.
- New independent ZIP extraction: first launch exit **0**, packaged smoke exit **0**, **15 checks PASS**, including real RapidOCR CPU inference and PDFium. Fresh config contains UI preferences only, no Recent Projects or development paths.
- Final portable ZIP privacy audit: **PASS**, 0 actionable findings. 106 informational vendor build-path markers do not match this build host. Application theme bytecode is not bundled.
- YAML parsing for workflows/templates: PASS. GitHub-hosted CI and real visible Windows UI are **NOT TESTED** in this task; they remain owner-run checks. No Computer Use was used.

## Sole current release candidate

`dist/Links-Manga-Studio-0.5.0-windows-x64.zip` — **163,307,681 bytes**.

SHA256: `2AB3C7CFEAAED4E821B68B8F005A14365E10C07AC5352034EECBB9ACB680BE6F`.

The adjacent `.zip.sha256` matches. Earlier v0.5.0 hashes and packaging statuses in Internal Development History are **superseded / historical**. No earlier hash should be used for this package. ZIP remains ignored by source Git and is intended only as an owner-uploaded Release asset.

## Owner next steps

Use MANUAL_GITHUB_PUBLISH.md and GITHUB_RELEASE_CHECKLIST.md: independent repository copy, staging/privacy review, visible acceptance, manual repository creation/push, remote CI, security/conduct contact, and manual Release. No main-license or exact-model permission decision remains pending for these reviewed artifacts; changes to dependencies/models require a new review.
