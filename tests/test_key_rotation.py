import os
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from src.gws_assistant.models import AppConfigModel
from src.gws_assistant.intent_parser import IntentParser

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def config():
    return AppConfigModel(
        provider="openrouter",
        model="google/gemini-2.0-flash-exp:free",
        api_key="key1",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        gws_binary_path=Path("gws"),
        log_file_path=Path("logs/test.log"),
        log_level="INFO",
        verbose=True,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        openrouter_api_keys=["key1", "key2", "key3"]
    )

def test_rotate_api_key_method(config):
    assert config.api_key == "key1"
    
    config.rotate_api_key()
    assert config.api_key == "key2"
    assert os.environ["OPENROUTER_API_KEY"] == "key2"
    
    config.rotate_api_key()
    assert config.api_key == "key3"
    assert os.environ["OPENROUTER_API_KEY"] == "key3"
    
    config.rotate_api_key()
    assert config.api_key == "key1"
    assert os.environ["OPENROUTER_API_KEY"] == "key1"

@patch("openai.resources.chat.Completions.create")
def test_intent_parser_rotates_on_429(mock_create, mock_logger, config):
    # Mock rate limit error for first attempt, success for second
    # In reality OpenAI SDK raises RateLimitError, but we check for "429" in msg in our code
    mock_create.side_effect = [
        Exception("Rate limit reached (429)"),
        MagicMock(choices=[MagicMock(message=MagicMock(content='{"service": "gmail", "action": "send_message"}'))])
    ]
    
    parser = IntentParser(config, mock_logger)
    # Ensure client is using initial key
    assert parser.client.api_key == "key1"
    
    with patch("time.sleep"):
        intent = parser.parse("send an email")
        
        assert intent.service == "gmail"
        # Verify rotation happened: config key updated AND client re-initialized
        assert config.api_key == "key2"
        assert parser.client.api_key == "key2"
        assert mock_create.call_count == 2
        mock_logger.warning.assert_any_call(
            "LLM rate limit detected in IntentParser. Rotating key and retrying in %ds...", 1
        )
