# Links Manga Studio v0.5.0 — Initial Public Release

Links Manga Studio is a local-first Windows workspace for manga OCR, translation, cleaning and typesetting. Created by **Links Tam**.

## Highlights

- Import image files, folders and PDFs. A PDF can create a project directly.
- Review local OCR text, translate by TextBlock or DOCX batch, erase text and refill the same area.
- Use project font styles, Auto Fit, Quality Check and named Undo/Redo actions.
- Switch Dark, Light or System appearance and Chinese/English UI.
- Keep `.lmw` project data local; source files can be copied or referenced.

## Install

After the owner publishes the release, download `Links-Manga-Studio-0.5.0-windows-x64.zip` and its `.sha256` file from GitHub Release assets. Verify the checksum, extract the entire ZIP and run `LinksMangaWorkspace.exe`. Keep `runtime/` beside it. The executable retains a legacy filename for compatibility; the application is named Links Manga Studio.

## Limitations

Windows x64 is the validated release target. OCR needs review, vertical text and complex erasing may need manual correction, and similar font recommendations are approximate. The portable build has no code signature. The tool provides no manga content; users are responsible for rights to the material they process.

## Checksums and credits

The final ZIP checksum is supplied in the adjacent `.sha256` release asset. Third-party notices are in the ZIP's `licenses/` folder and in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). OCR model licensing is documented separately in [MODEL_LICENSES.md](MODEL_LICENSES.md).

**License:** Apache-2.0 for project code and original assets. All three bundled OCR artifacts match the upstream Apache-2.0 model notice by SHA256. This is the first public-release candidate; publication is performed manually by Links Tam. Perform visible Windows acceptance and check GitHub CI before publishing.
