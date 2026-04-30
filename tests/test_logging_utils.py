from __future__ import annotations

import pytest
pytestmark = pytest.mark.gmail

import logging
import os
import tempfile
from pathlib import Path
from logging.handlers import RotatingFileHandler
from unittest.mock import MagicMock

from rich.logging import RichHandler

from gws_assistant.logging_utils import setup_logging


def _close_handlers(logger: logging.Logger):
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()


def test_setup_logging_standard_level():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = MagicMock()
        config.log_level = "DEBUG"
        config.log_file_path = tmp_path / "test.log"

        logger = setup_logging(config)

        try:
            assert logger.name == "gws_assistant"
            assert logger.level == logging.DEBUG
            assert not logger.propagate
            assert len(logger.handlers) == 2

            handlers_types = {type(h) for h in logger.handlers}
            assert handlers_types == {RichHandler, RotatingFileHandler}

            rich_handler = next(h for h in logger.handlers if isinstance(h, RichHandler))
            file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

            assert rich_handler.level == logging.DEBUG
            assert file_handler.level == logging.DEBUG
        finally:
            _close_handlers(logger)


def test_setup_logging_info_level():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = MagicMock()
        config.log_level = "INFO"
        config.log_file_path = tmp_path / "test.log"

        logger = setup_logging(config)
        try:
            rich_handler = next(h for h in logger.handlers if isinstance(h, RichHandler))
            file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

            assert rich_handler.level == logging.INFO
            assert file_handler.level == logging.INFO
        finally:
            _close_handlers(logger)


def test_setup_logging_warning_level():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = MagicMock()
        config.log_level = "WARNING"
        config.log_file_path = tmp_path / "test.log"

        logger = setup_logging(config)
        try:
            rich_handler = next(h for h in logger.handlers if isinstance(h, RichHandler))
            file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

            assert rich_handler.level == logging.WARNING
            assert file_handler.level == logging.INFO
        finally:
            _close_handlers(logger)


def test_setup_logging_off_level():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for level in ("NONE", "OFF"):
            config = MagicMock()
            config.log_level = level
            config.log_file_path = tmp_path / f"test_{level}.log"

            logger = setup_logging(config)
            try:
                rich_handler = next(h for h in logger.handlers if isinstance(h, RichHandler))
                file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

                assert rich_handler.level == 100
                assert file_handler.level == logging.INFO
            finally:
                _close_handlers(logger)


def test_setup_logging_invalid_level():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = MagicMock()
        config.log_level = "INVALID_LEVEL"
        config.log_file_path = tmp_path / "test.log"

        # Should default to INFO for console
        logger = setup_logging(config)
        try:
            rich_handler = next(h for h in logger.handlers if isinstance(h, RichHandler))
            file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

            assert rich_handler.level == logging.INFO
            assert file_handler.level == logging.INFO
        finally:
            _close_handlers(logger)
