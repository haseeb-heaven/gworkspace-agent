"""Negative test cases for file operations to ensure robust error handling."""

import logging
from pathlib import Path

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.models import AppConfigModel
from gws_assistant.planner import CommandPlanner


@pytest.fixture
def config():
    return AppConfigModel(
        provider="openai",
        model="gpt-4o",
        api_key="fake",
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=Path("gws"),
        log_file_path=Path("logs/test.log"),
        log_level="INFO",
        verbose=False,
        env_file_path=None,
        setup_complete=True,
        max_retries=3,
        langchain_enabled=False,
        use_heuristic_fallback=True,
        default_recipient_email="test@example.com",
        read_only_mode=False,
        sandbox_enabled=False,
    )

@pytest.fixture
def logger():
    return logging.getLogger("test_negative")

def test_upload_non_existent_file_logic(config, logger):
    """Ensure CommandPlanner validates file existence during command building."""
    planner = CommandPlanner()
    params = {"file_path": "non_existent_file_123.txt"}
    with pytest.raises(ValidationError, match="File not found"):
        planner.build_command("drive", "upload_file", params)

def test_export_extension_fallback():
    """Ensure export logic handles unknown MIME types gracefully by falling back to .dat or .txt."""
    from gws_assistant.file_types import export_extension_for_mime
    # Unknown binary -> .dat
    assert export_extension_for_mime("application/x-unknown-weird") == ".dat"
    # Unknown text -> .txt
    assert export_extension_for_mime("text/weird") == ".txt"
    # Known ones still work
    assert export_extension_for_mime("application/pdf") == ".pdf"

def test_invalid_file_path_regex_parsing(config, logger):
    """Test that special characters in quoted paths are correctly parsed by RE_FILE_PATH."""
    from gws_assistant.file_types import RE_FILE_PATH

    text = "upload file 'C:/Users/hasee/Desktop/File with + and [].txt' to drive"
    match = RE_FILE_PATH.search(text)
    assert match is not None
    assert match.group(1) == "C:/Users/hasee/Desktop/File with + and [].txt"

def test_unc_path_regex_parsing(config, logger):
    """Test that UNC paths are correctly parsed by the improved RE_FILE_PATH."""
    from gws_assistant.file_types import RE_FILE_PATH

    text = "upload file '\\\\server\\share\\folder\\file.txt' to drive"
    match = RE_FILE_PATH.search(text)
    assert match is not None
    path = next(g for g in match.groups() if g is not None)
    assert path == "\\\\server\\share\\folder\\file.txt"
