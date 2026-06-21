"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import LOGS_DIR, ensure_directories


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure console and rotating file logging once."""
    ensure_directories()
    logger = logging.getLogger("ai_video_clipper")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the configured application logger."""
    setup_logging()
    return logging.getLogger(f"ai_video_clipper.{name}")
