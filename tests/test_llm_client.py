import pytest
from unittest.mock import patch, MagicMock
from litellm.exceptions import RateLimitError, AuthenticationError
from gws_assistant.llm_client import call_llm

pytestmark = pytest.mark.llm

def _make_config(model, fallbacks=None, keys=None):
    cfg = MagicMock()
    cfg.model = model
    cfg.llm_fallback_models = fallbacks or []
    cfg.openrouter_api_keys = keys or ["test-key"]
    cfg.api_key = "test-key"
    cfg.base_url = "https://openrouter.ai/api/v1"
    cfg.groq_api_key = None
    cfg.ollama_api_base = None
    cfg.timeout_seconds = 10
    return cfg

@patch("gws_assistant.llm_client.completion")
def test_successful_call(mock_completion):
    mock_completion.return_value = MagicMock()
    cfg = _make_config("openrouter/nvidia/nemotron-super-49b-v1:free")
    result = call_llm([{"role": "user", "content": "hi"}], cfg)
    assert result is not None

@patch("gws_assistant.llm_client.completion")
def test_fallback_on_rate_limit(mock_completion):
    mock_completion.side_effect = [
        RateLimitError("rate limited", llm_provider="openrouter", model="x"),
        MagicMock(),  # fallback succeeds
    ]
    cfg = _make_config(
        "openrouter/nvidia/nemotron-super-49b-v1:free",
        fallbacks=["groq/llama3-groq-70b-8192-tool-use-preview"],
    )
    cfg.groq_api_key = "groq-test-key"
    result = call_llm([{"role": "user", "content": "hi"}], cfg)
    assert mock_completion.call_count == 2

@patch("gws_assistant.llm_client.completion")
def test_all_models_exhausted_raises(mock_completion):
    mock_completion.side_effect = RateLimitError(
        "rate limited", llm_provider="openrouter", model="x"
    )
    cfg = _make_config("openrouter/nvidia/nemotron-super-49b-v1:free")
    with pytest.raises(RuntimeError, match="All LLM models exhausted"):
        call_llm([{"role": "user", "content": "hi"}], cfg)
