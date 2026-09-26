"""Persist appearance preference and apply it without recreating the workspace."""
import sys

from PySide6.QtWidgets import QApplication

from .tokens import DARK, LIGHT, stylesheet

MODES = ("dark", "light", "system")


def system_is_light() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return bool(value)
    except (OSError, ValueError):
        return False


class ThemeManager:
    def __init__(self, config):
        self.config = config
        self.mode = config.data.get("theme", "dark")
        if self.mode not in MODES:
            self.mode = "dark"

    @property
    def effective(self) -> str:
        if self.mode == "system":
            return "light" if system_is_light() else "dark"
        return self.mode

    @property
    def tokens(self) -> dict[str, str]:
        return LIGHT if self.effective == "light" else DARK

    def apply(self) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet(self.tokens))

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown theme: {mode}")
        self.mode = mode
        self.config.data["theme"] = mode
        self.config.save()
        self.apply()
