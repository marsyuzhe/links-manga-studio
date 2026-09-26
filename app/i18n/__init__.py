"""Central UI language manager."""
from __future__ import annotations
import json
from PySide6.QtCore import QObject, QLocale, Signal
from app.resources import resource_path

SUPPORTED = ("zh_CN", "en_US")


def default_language(system_locale: str | None = None) -> str:
    locale = (system_locale or QLocale.system().name()).replace("-", "_").lower()
    return "zh_CN" if locale in ("zh_cn", "zh_sg") else "en_US"


class LanguageManager(QObject):
    changed = Signal(str)

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self.catalogs = {
            language: json.loads(resource_path(f"app/i18n/locales/{language}.json").read_text(encoding="utf-8"))
            for language in SUPPORTED
        }
        saved = config.data.get("language", "auto")
        self.language = default_language() if saved == "auto" else saved if saved in SUPPORTED else "en_US"

    def tr(self, key: str, **values) -> str:
        string = self.catalogs[self.language].get(key, self.catalogs["en_US"].get(key, key))
        try:
            return string.format(**values)
        except (KeyError, ValueError):
            return string

    def set_language(self, language: str) -> None:
        target = language if language in SUPPORTED else "en_US"
        self.config.data["language"] = target
        self.config.save()
        if target != self.language:
            self.language = target
            self.changed.emit(target)

    def display_label(self, page: dict) -> str:
        """Render the generated default label locally without modifying project data."""
        original = page["label"]
        if original == f"第 {page['display_order']} 页":
            return self.tr("page.default_label", number=page["display_order"])
        return original

    def user_error(self, message: str) -> str:
        for prefix, key in (("Enter a valid project name", "error.invalid_name"),
                            ("Project directory already exists:", "error.project_exists"),
                            ("Cannot create project at", "error.create_project"),
                            ("Cannot open project", "error.open_project"),
                            ("project.json does not match", "error.project_mismatch"),
                            ("Source mode must", "error.source_mode")):
            if message.startswith(prefix):
                return self.tr(key, detail=message)
        return self.tr("error.details", detail=message)

    def progress_text(self, text: str) -> str:
        for prefix, key in (("Validating ", "progress.validating"),
                            ("Preparing ", "progress.preparing"),
                            ("Relocating ", "progress.relocating")):
            if text.startswith(prefix):
                return self.tr(key, filename=text[len(prefix):])
        return self.tr(text) if text.startswith("status.") else text
