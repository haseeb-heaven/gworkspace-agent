import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from gws_assistant.setup_wizard import discover_gws_binary, _render_env, _quote, _ask_text, _ask_secret

def test_discover_gws_binary_path_env():
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/gws"
        # Expand user and resolve would fail on fake paths, so we mock them if needed
        # but discover_gws_binary uses exists() check
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_file", return_value=True):
                result = discover_gws_binary()
                assert result is not None

def test_render_env():
    values = {
        "LLM_PROVIDER": "openai",
        "OPENROUTER_API_KEY": "sk-123",
        "OPENROUTER_MODEL": "gpt-4o",
        "OPENROUTER_BASE_URL": "http://api.com",
        "TAVILY_API_KEY": "tv-123",
        "DEFAULT_RECIPIENT_EMAIL": "test@test.com",
        "LANGCHAIN_ENABLED": "true",
        "CODE_EXECUTION_ENABLED": "true",
        "CODE_EXECUTION_BACKEND": "subprocess",
        "CODE_EXECUTION_TIMEOUT_SECONDS": "10",
        "CODE_EXECUTION_MEMORY_MB": "64",
        "CODE_EXECUTION_MAX_OUTPUT": "8192",
        "CODE_EXECUTION_DOCKER_IMAGE": "img",
        "CODE_EXECUTION_DOCKER_BINARY": "docker",
        "E2B_API_KEY": "e2b-123",
        "GWS_BINARY_PATH": "/path/to/gws",
        "APP_LOG_LEVEL": "INFO",
        "APP_VERBOSE": "true",
        "APP_LOG_DIR": "logs",
        "LLM_TIMEOUT_SECONDS": "30",
        "MAX_RETRIES": "3"
    }
    rendered = _render_env(values)
    assert "LLM_PROVIDER='openai'" in rendered
    assert "GWS_BINARY_PATH='/path/to/gws'" in rendered

def test_quote():
    assert _quote("") == ""
    assert _quote("hello") == "'hello'"
    assert _quote("don't") == "'don\\'t'"

@patch("gws_assistant.setup_wizard.Prompt.ask")
def test_ask_text(mock_ask):
    mock_ask.return_value = "  hello  "
    assert _ask_text("prompt", "default") == "hello"

@patch("gws_assistant.setup_wizard.Prompt.ask")
def test_ask_secret(mock_ask):
    mock_ask.return_value = "secret"
    assert _ask_secret("prompt", "existing") == "secret"
    
    mock_ask.return_value = ""
    assert _ask_secret("prompt", "existing") == "existing"
