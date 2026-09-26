# License review — Apache-2.0 adopted

On 2026-09-26 the owner authorized Apache License 2.0 for Links Manga Studio source, documentation and original project assets. Root LICENSE is the complete unchanged official text; NOTICE records Copyright 2026 Links Tam and separate upstream attribution. Contributors retain their rights. This review is a technical inventory, not legal advice.

## PDF architecture

Application rendering uses pypdfium2 / PDFium. PyMuPDF was removed from test extras and build requirements. Blank test PDFs now use PDFium; drawn synthetic fixtures use existing Qt QPdfWriter. The environment was uninstalled of PyMuPDF and affected tests passed. Build exclusions for pymupdf/fitz remain defensive safeguards.

## Runtime obligations

Apache-2.0 permits commercial use and redistribution subject to its conditions and does not mandate publishing every derivative's source. Preserve LICENSE, NOTICE and relevant upstream notices, identify modified files, and respect the standard patent and trademark provisions.

Qt/PySide6 retains LGPL/GPL/commercial terms. The onedir package keeps DLLs separate with notices and upstream source pointers; provide the applicable LGPL materials and permit replacement with compatible modified libraries. PDFium and other libraries retain their own notices. Apache-2.0 for this project does not relicense them.

## Models

All three bundled OCR weight hashes match RapidOCR's explicit artifact notice under Apache-2.0. See MODEL_LICENSES.md and licenses/RapidOCR. The earlier OWNER DECISION REQUIRED status was superseded by primary evidence on 2026-09-26.

GitHub publication remains entirely owner-controlled. The source/license preparation is complete; visible Windows acceptance and remote CI are separate user-run checks.
