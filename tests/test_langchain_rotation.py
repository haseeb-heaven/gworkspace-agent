import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.langchain_agent import plan_with_langchain
from gws_assistant.models import AppConfigModel


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def config():
    return AppConfigModel(
        provider="openrouter",
        model="google/gemini-2.0-flash-exp:free",
        api_key="key1",
        llm_fallback_models=[],
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        gws_binary_path=Path("gws"),
        log_file_path=Path("logs/test.log"),
        log_level="INFO",
        file_log_level="DEBUG",
        verbose=True,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        llm_api_keys=["key1", "key2", "key3"],
    )


@patch("gws_assistant.langchain_agent.create_agent")
def test_langchain_rotates_on_429(mock_create_agent, mock_logger, config):
    # Mock LLM chain to fail with 429 then succeed
    mock_llm = MagicMock()
    mock_create_agent.return_value = mock_llm

    mock_structured_output = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured_output

    # The chain is (prompt | mock_structured_output)
    # We can mock the result of the pipe directly
    with patch("langchain_core.prompts.chat.ChatPromptTemplate.__or__") as mock_or:
        mock_or.return_value = mock_structured_output

        mock_structured_output.invoke.side_effect = [
            Exception("Rate limit reached (429)"),
            {
                "tasks": [
                    {
                        "id": "t1",
                        "service": "gmail",
                        "action": "send_message",
                        "parameters": {"to_email": "test@example.com", "subject": "Test", "body": "Hello"},
                    }
                ],
                "summary": "done",
            },
        ]

        with patch("time.sleep"):
            plan = plan_with_langchain("send email to test@example.com", config, mock_logger)

        assert plan is not None

        assert len(plan.tasks) == 1
        # Verify rotation happened in config
        assert config.api_key == "key2"
        # Verify it retried
        assert mock_llm.with_structured_output.return_value.invoke.call_count == 2
        mock_logger.info.assert_any_call(
            "Model '%s' rate-limited (attempt %d/%d, HTTP 429). Rotating API key and backing off %.0fs before retry.",
            "google/gemini-2.0-flash-exp:free",
            1,
            3,
            2.0,
        )
