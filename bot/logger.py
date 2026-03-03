"""Centralized logging configuration for the Discord music bot."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR: Path = Path(__file__).parent.parent / 'logs'


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with a console handler and a rotating file handler.

    Call this once at startup (before the bot connects) to ensure all loggers
    created with :func:`get_logger` inherit these handlers.
    """
    LOG_DIR.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    # Rotate at 10 MB, keep 5 backup files
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / 'bot.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger — typically called with ``__name__``."""
    return logging.getLogger(name)
