from __future__ import annotations

from gws_assistant.config import AppConfig


def test_config_prefers_openrouter_when_openrouter_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    config = AppConfig.from_env()
    assert config.provider == "openrouter"
    assert config.api_key == "or-key"
    assert "openrouter.ai" in (config.base_url or "")


def test_config_uses_openai_when_provider_is_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = AppConfig.from_env()
    assert config.provider == "openai"
    assert config.api_key == "oa-key"
    assert config.model
