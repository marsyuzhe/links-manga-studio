# Links Manga Studio 0.6.0 — User guide

## Install and create

Extract the entire portable ZIP and run LinksMangaWorkspace.exe. New Project chooses a name and location. Copy mode owns imported sources; Reference mode retains paths to originals. Recent Projects reopens known folders.

## Import and navigate

Import images, a folder or PDF from the toolbar, or drag files into the window. Without a project, PDF import starts project creation. Select pages on the left; Previous/Next navigate. Fit shows the whole image; 100% uses actual pixels. Zoom and pan for details.

## OCR and review

Choose a page/batch/project scope and run OCR. Review source text and reading order in the text panel. OCR quality varies. Re-running OCR preserves matched identities; back up important projects first.

## Translation

Select a TextBlock and enter its translation on the right. No service account is required. Export source text for external review, or use Word exchange without changing text IDs or protocol fields.

Translation Center optionally uses your cloud API, Ollama or a local compatible server. Enter credentials privately. Local servers must already be running with a model; model refresh does not download models. Cloud requests send selected text and enabled context. Review drafts; manual translations are protected by default.

## Clean and typeset

Clean selected regions without deleting TextBlocks or translations. Fill the same region using its translation. Choose installed fonts/style and inspect layout/overflow. Use Undo/Redo for supported edits. Quality checks run on explicit action.

## Export and troubleshooting

Export the available image/archive formats to a new folder. PDF import does not imply finished PDF export. Keep complete project backups and referenced originals.

Missing source: locate the original file. OCR failure: check models and logs. HTTP 401: check key and endpoint; 429: reduce concurrency and follow provider limits. Local connection: check server/address/model. Missing font: install a suitable licensed font. Overflow: shorten text, enlarge the region or adjust style.

Help → Diagnostics gives environment details; Open Log Folder opens logs. Remove private paths/text before sharing. Startup does not contact translation providers.

Detailed Chinese guide: docs/USER_GUIDE.zh-CN.md in source; USER_GUIDE.zh-CN.md alongside the portable EXE. Automated verification does not replace real Windows/service acceptance.
