from __future__ import annotations

from unittest.mock import patch

import pytest

from gws_assistant.config import AppConfig


@pytest.fixture(autouse=True)
def clear_config_cache():
    AppConfig.clear_cache()
    yield
    AppConfig.clear_cache()


def _required(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "EMAIL_ADDRESS")
    monkeypatch.setenv("GWS_BINARY_PATH", "GWS_BINARY_PATH")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "openrouter/nvidia/nemotron-super-49b-v1:free")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")


def test_config_prefers_openrouter_when_openrouter_key_present(monkeypatch):
    _required(monkeypatch)
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY1", raising=False)
    monkeypatch.delenv("LLM_API_KEY2", raising=False)
    monkeypatch.delenv("LLM_API_KEY3", raising=False)

    # Set test values
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")

    # Patch load_dotenv to prevent loading from .env file
    with patch("gws_assistant.config.load_dotenv"):
        config = AppConfig.from_env()
    assert config.provider == "openrouter"
    assert config.api_key == "or-key"
    assert "openrouter.ai" in (config.base_url or "")


def test_config_generic_llm_env_overrides_provider_specific(monkeypatch):
    _required(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "openrouter/qwen/qwen3-next-80b-a3b-instruct:free")
    monkeypatch.setenv("LLM_API_KEY", "generic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "generic")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("USE_HEURISTIC_FALLBACK", "true")
    with patch("gws_assistant.config.load_dotenv"):
        config = AppConfig.from_env()
    assert config.model == "openrouter/qwen/qwen3-next-80b-a3b-instruct:free"
    assert config.api_key == "generic"
    assert config.use_heuristic_fallback is True


def test_config_provider_specific_model_fallback_for_openrouter(monkeypatch):
    _required(monkeypatch)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/deepseek/deepseek-chat:free")
    # Make sure we don't accidentally load LLM_MODEL from local .env
    monkeypatch.setenv("LLM_MODEL", "")
    with patch("gws_assistant.config.load_dotenv"):
        config = AppConfig.from_env()
    assert config.model == "openrouter/deepseek/deepseek-chat:free"


def test_config_includes_code_execution_flag(monkeypatch):
    _required(monkeypatch)
    monkeypatch.setenv("CODE_EXECUTION_ENABLED", "false")
    with patch("gws_assistant.config.load_dotenv"):
        config = AppConfig.from_env()
    assert config.code_execution_enabled is False
