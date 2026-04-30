"""Unit tests for llm_client.py — covers helper functions and call_llm logic."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from litellm.exceptions import RateLimitError, AuthenticationError

from gws_assistant.llm_client import _build_api_kwargs, call_llm


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.model = "openrouter/google/gemini-2.0-flash-001"
    config.api_key = "test_key"
    config.base_url = "https://openrouter.ai/api/v1"
    config.timeout_seconds = 30
    config.temperature = 0.0
    config.max_tokens = 100
    config.llm_fallback_models = []
    config.llm_api_keys = []
    return config


def test_build_api_kwargs_openrouter(mock_config):
    kwargs = _build_api_kwargs("openrouter/test", mock_config)
    assert kwargs["api_key"] == "test_key"
    assert kwargs["api_base"] == "https://openrouter.ai/api/v1"


def test_build_api_kwargs_groq(mock_config):
    mock_config.groq_api_key = "groq_key"
    kwargs = _build_api_kwargs("groq/test", mock_config)
    assert kwargs["api_key"] == "groq_key"


def test_build_api_kwargs_ollama(mock_config):
    mock_config.ollama_api_base = "https://ollama.example:11434"
    kwargs = _build_api_kwargs("ollama/test", mock_config)
    assert kwargs["api_base"] == "https://ollama.example:11434"
    assert kwargs["api_key"] == "ollama"


@patch("gws_assistant.llm_client.completion")
def test_call_llm_success(mock_completion, mock_config):
    mock_completion.return_value = {"id": "resp1"}
    resp = call_llm([{"role": "user", "content": "hi"}], mock_config)
    assert resp == {"id": "resp1"}
    assert mock_completion.called


@patch("gws_assistant.llm_client.completion")
def test_call_llm_fallback(mock_completion, mock_config):
    mock_config.llm_fallback_models = ["fallback-1"]
    # First call fails with RateLimit, second succeeds
    mock_completion.side_effect = [
        RateLimitError("Rate limit", model="p", llm_provider="p"),
        {"id": "resp_fallback"}
    ]
    resp = call_llm([{"role": "user", "content": "hi"}], mock_config)
    assert resp == {"id": "resp_fallback"}
    assert mock_completion.call_count == 2


@patch("gws_assistant.llm_client.completion")
def test_call_llm_exhausted(mock_completion, mock_config):
    mock_completion.side_effect = AuthenticationError("Auth failed", model="p", llm_provider="p")
    with pytest.raises(RuntimeError, match="All LLM models exhausted"):
        call_llm([{"role": "user", "content": "hi"}], mock_config)
