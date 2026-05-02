import os
from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.tools.telegram import redact_sensitive, send_telegram


@pytest.fixture(autouse=True)
def mock_telegram_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654321")
    
    from gws_assistant.config import AppConfig
    AppConfig.clear_cache()
    
    with patch("gws_assistant.config.load_dotenv"), \
         patch("gws_assistant.tools.telegram.load_dotenv"), \
         patch("dotenv.load_dotenv"):
        yield
    
    AppConfig.clear_cache()


def test_redact_sensitive():
    # Test pattern matching
    assert redact_sensitive("sk-12345678901234567890") == "[REDACTED]"
    assert redact_sensitive("Bearer 12345.67890.abcde") == "[REDACTED]"

    # Test env var matching
    with patch.dict(os.environ, {"MY_SECRET_TOKEN": "supersecret"}):
        assert redact_sensitive("my token is supersecret") == "my token is [REDACTED]"

def test_send_telegram_missing_config():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=True):
        assert send_telegram("hello") is False

@patch("urllib.request.urlopen")
@patch("urllib.request.Request")
def test_send_telegram_success(mock_request, mock_urlopen):
    # Mock urlopen context manager
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = b'{"ok": true}'
    mock_urlopen.return_value = mock_response

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "456"}):
        assert send_telegram("hello") is True
        mock_urlopen.assert_called_once()

@patch("urllib.request.urlopen")
def test_send_telegram_failure(mock_urlopen):
    from urllib.error import URLError
    mock_urlopen.side_effect = URLError("failed")

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "456"}):
        assert send_telegram("hello") is False
