from __future__ import annotations

from unittest.mock import patch

import pytest

from gws_assistant.config import AppConfig


@pytest.fixture(autouse=True)
def clear_config_cache():
    AppConfig.clear_cache()
    yield
    AppConfig.clear_cache()


def _required(monkeypatch):
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "recipient@example.test")
    monkeypatch.setenv("GWS_BINARY_PATH", r"d:\Code\gworkspace-agent\gws.exe")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "openrouter/nvidia/nemotron-super-49b-v1:free")


def test_config_prefers_openrouter_when_openrouter_key_present(monkeypatch):
    _required(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with patch("gws_assistant.config.load_dotenv"):
        config = AppConfig.from_env()
    assert config.provider == "openrouter"
    assert config.api_key == "or-key"
    assert "openrouter.ai" in (config.base_url or "")


def test_config_generic_llm_env_overrides_provider_specific(monkeypatch):
    _required(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "openrouter/qwen/qwen3-next-80b-a3b-instruct:free")
    monkeypatch.setenv("LLM_API_KEY", "generic")
    monkeypatch.setenv("OPENAI_API_KEY", "generic")
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
