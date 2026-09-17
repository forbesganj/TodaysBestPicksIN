"""
Logging setup: logs to console (visible in GitHub Actions run logs)
and to a rotating file under data/bot.log (persisted via git commit
by the workflow, so you get history without any external service).
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_file: str) -> logging.Logger:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger("deals_bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Keep file small: 1MB, 2 backups. GitHub Actions commits this back,
    # so we don't want it growing the repo unbounded.
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
