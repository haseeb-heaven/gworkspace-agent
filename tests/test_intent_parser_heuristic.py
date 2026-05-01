import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.intent_parser import IntentParser
from gws_assistant.models import AppConfigModel


@pytest.fixture
def parser():
    config = AppConfigModel(
        provider="openai",
        model="gpt-4o",
        api_key=None,
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=Path("/fake/gws"),
        log_file_path=Path("gws.log"),
        log_level="INFO",
        verbose=False,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=False,
    )
    logger = logging.getLogger("test")
    return IntentParser(config, logger)

def test_parse_empty(parser):
    result = parser.parse("")
    assert result.needs_clarification is True

def test_parse_gmail_list(parser):
    result = parser.parse("show my emails about invoice", force_heuristic=True)
    assert result.service == "gmail"

def test_parse_gmail_send(parser):
    result = parser.parse("send email to test@example.com with subject 'Hello'", force_heuristic=True)
    assert result.service == "gmail"

def test_parse_drive_list(parser):
    result = parser.parse("list my files in drive", force_heuristic=True)
    assert result.service == "drive"

def test_parse_docs_create(parser):
    result = parser.parse("create a document named 'My Report'", force_heuristic=True)
    assert result.service in ("docs", "drive")

def test_parse_sheets_create(parser):
    result = parser.parse("create a spreadsheet named 'Budget'", force_heuristic=True)
    assert result.service == "sheets"

def test_parse_calendar_list(parser):
    result = parser.parse("list my calendar events", force_heuristic=True)
    assert result.service == "calendar"

def test_parse_tasks_list(parser):
    result = parser.parse("list my tasks", force_heuristic=True)
    assert result.service == "tasks"

def test_parse_keep_list(parser):
    result = parser.parse("list my keep notes", force_heuristic=True)
    assert result.service == "keep"

def test_parse_contacts_list(parser):
    result = parser.parse("list my contacts", force_heuristic=True)
    assert result.service == "contacts"

def test_parse_forms_list(parser):
    result = parser.parse("list my forms", force_heuristic=True)
    assert result.service == "forms"

def test_parse_slides_list(parser):
    result = parser.parse("list my slides", force_heuristic=True)
    assert result.service == "slides"

def test_parse_classroom_list(parser):
    result = parser.parse("list my courses", force_heuristic=True)
    assert result.service == "classroom"

def test_parse_with_llm_success(parser):
    # Mock self.client
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content='{"service": "gmail", "action": "send_message", "parameters": {"to": "a@b.com"}, "confidence": 0.9}'))]
    mock_client.chat.completions.create.return_value = mock_completion

    with patch.object(parser, "client", mock_client):
        result = parser.parse("send mail to a@b.com")
        assert result.service == "gmail"
        assert result.confidence == 0.9

def test_build_client_exception(parser):
    with patch("gws_assistant.intent_parser.OpenAI") as mock_openai:
        mock_openai.side_effect = Exception("failed")
        parser.config.api_key = "test"
        client = parser._build_client()
        assert client is None
