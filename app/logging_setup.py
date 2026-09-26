"""Application logging and uncaught exception recording."""
import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "app.log"
    logging.basicConfig(filename=path, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True,
                        encoding="utf-8")

    def record_exception(exc_type, exc, tb):
        logging.getLogger("app").critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = record_exception
    logging.info("Application logging started")
    return path

