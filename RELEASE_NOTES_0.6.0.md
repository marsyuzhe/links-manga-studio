# Links Manga Studio v0.6.0

Local-first manga OCR, translation, cleaning and typesetting studio for Windows.

Created by Links Tam.

## Included

- Image/folder/PDF import, local projects and stable page/text IDs.
- Local OCR, source review, manual translation, cleaning, typesetting and exports.
- Translation Center with optional user-configured cloud APIs or external local model services.
- Project terminology/characters, task history, review and protected manual edits.
- Dark/light workspace polish, keyboard navigation and bounded image cache.
- Final preparation: secondary views load on demand, hidden translation polling stops, history loads in groups of 100.
- User/developer guides and dependency/model license notices.

## Download

Download **Links-Manga-Studio-0.6.0-windows-x64.zip**, extract the complete folder and run **LinksMangaWorkspace.exe**. Keep runtime/ beside it. The SHA256 asset identifies the ZIP. GitHub's source archives are not the portable application.

## Privacy and compatibility

OCR and manual work are local. Cloud translation sends selected text and enabled context to your configured service. You supply API keys; Windows Credential Manager stores them. Local servers/models are installed and started separately. No LLM weights are bundled.

Back up projects and referenced originals before upgrading. Page/Text UID and Word protocol remain unchanged. Migrated projects must not be written by older executables; roll back using a complete pre-upgrade copy.

## Verification and limitations

Automated regression, simulated geometry, synthetic thousand-page performance and extracted portable smoke checks are recorded locally. Mock services verify protocols, not real providers/models.

Real paid API, actual local model, visible Windows interaction and system DPI are **NOT TESTED** in this preparation pass. OCR depends on source quality. Drafts require review; unavailable token usage is unknown. PDF import does not imply finished PDF export. Native provider protocols beyond the app's available options are unsupported. The executable is unsigned.

## License

Apache-2.0 for app source. Dependencies and OCR models retain separate licenses; see packaged notices and licenses/.
