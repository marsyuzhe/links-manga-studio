"""Run with python -m app.main."""
import logging
import os
import sys
import argparse
import json
from pathlib import Path
import ctypes

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from .config import Config, config_dir
from .logging_setup import setup_logging
from .project import ProjectService
from .ui.window import MainWindow
from .resources import resource_path
from .session import SessionGuard
from .branding import DISPLAY_NAME, INTERNAL_APP_ID


def configure_application_icon(app: QApplication) -> None:
    app.setWindowIcon(QIcon(str(resource_path("assets/icons/app_icon.ico"))))


def main() -> int:
    parser = argparse.ArgumentParser(description=DISPLAY_NAME)
    parser.add_argument("--project", type=Path, help="Open an existing .lmw project")
    parser.add_argument("--smoke-test", action="store_true", help="Run packaged runtime checks and exit")
    parser.add_argument("--smoke-output", type=Path, help="Write release smoke result JSON")
    arguments = parser.parse_args()
    log_path = setup_logging(config_dir() / "logs")
    session = SessionGuard(config_dir())
    session.start()
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(INTERNAL_APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName(DISPLAY_NAME)
    configure_application_icon(app)
    window = MainWindow(ProjectService(Config()), log_path)
    window.show()
    if session.previous_unclean:
        logging.warning("Previous session ended unexpectedly")
        window.statusBar().showMessage("Previous session ended unexpectedly — check logs and unfinished tasks")
    if arguments.project:
        window.open_project(arguments.project)
    logging.info("Main window shown")
    smoke_exit = 0
    if arguments.smoke_test:
        if arguments.smoke_output is None:
            parser.error("--smoke-test requires --smoke-output")
        try:
            from .release_smoke import run_release_smoke
            report = run_release_smoke(arguments.smoke_output)
            logging.info("Release smoke passed: %s", report)
        except Exception as exc:
            logging.exception("Release smoke failed")
            report = {"ok": False, "error": str(exc)}
            smoke_exit = 2
        arguments.smoke_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.smoke_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        QTimer.singleShot(0, app.quit)
    if os.environ.get("LMW_SMOKE_EXIT_MS"):
        QTimer.singleShot(int(os.environ["LMW_SMOKE_EXIT_MS"]), app.quit)
    try:
        result = app.exec()
        return smoke_exit or result
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
