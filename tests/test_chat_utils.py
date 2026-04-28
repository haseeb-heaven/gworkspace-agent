from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.chat_utils import get_chat_response
from gws_assistant.models import AppConfigModel

pytestmark = pytest.mark.drive

@pytest.fixture
def mock_config():
    return AppConfigModel(
        provider="openrouter",
        model="openrouter/free",
        api_key="test-key",
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=None,
        log_file_path=None,
        log_level="INFO",
        verbose=False,
        env_file_path=None,
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
    )

@pytest.mark.asyncio
async def test_get_chat_response_success(mock_config):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello there!"

    with patch("gws_assistant.chat_utils.call_llm", return_value=mock_response) as mock_call:
        response = await get_chat_response("hi", mock_config)

        assert response == "Hello there!"
        mock_call.assert_called_once()
        args, kwargs = mock_call.call_args
        assert kwargs["messages"][1]["content"] == "hi"
        assert kwargs["config"] == mock_config

@pytest.mark.asyncio
async def test_get_chat_response_error(mock_config):
    with patch("gws_assistant.chat_utils.call_llm", side_effect=RuntimeError("LLM failed")) as mock_call:
        response = await get_chat_response("hi", mock_config)

        assert "I encountered an error" in response
        assert "LLM failed" in response
        mock_call.assert_called_once()

@pytest.mark.asyncio
async def test_get_chat_response_empty(mock_config):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""

    with patch("gws_assistant.chat_utils.call_llm", return_value=mock_response):
        response = await get_chat_response("hi", mock_config)

        assert response == "I couldn't generate a response."
