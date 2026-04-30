"""Logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from .models import AppConfigModel


def setup_logging(config: AppConfigModel) -> logging.Logger:
    """Configures console and file log output."""
    logger = logging.getLogger("gws_assistant")

    # Map 'NONE' or 'OFF' to a very high level to silence everything
    requested_level = config.log_level.upper()
    if requested_level in ("NONE", "OFF"):
        console_level = 100  # Higher than CRITICAL
    else:
        console_level = getattr(logging, requested_level, logging.INFO)

    # The logger itself must be at least as verbose as the most verbose handler
    # We'll keep the logger at INFO (or lower) so the file handler gets data
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False,
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(console_level)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        filename=config.log_file_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    # File handler stays at INFO (or requested level if more verbose)
    file_handler.setLevel(min(console_level, logging.INFO))
    logger.addHandler(file_handler)

    logger.debug(f"Logging configured: console={requested_level}, file=INFO")
    return logger
