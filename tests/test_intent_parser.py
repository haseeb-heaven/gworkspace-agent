from __future__ import annotations

import logging

from gws_assistant.config import AppConfig
from gws_assistant.intent_parser import IntentParser


def test_heuristic_parser_detects_drive(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("GWS_BINARY_PATH", "gws")
    # Clear fallback models to avoid validation errors from user's .env
    # Set to empty string (not delete) to prevent load_dotenv from re-loading from .env
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "")
    monkeypatch.setenv("LLM_FALLBACK_MODEL2", "")
    monkeypatch.setenv("LLM_FALLBACK_MODEL3", "")
    # Clear config cache to ensure environment changes take effect
    AppConfig.clear_cache()
    config = AppConfig.from_env()
    parser = IntentParser(config=config, logger=logging.getLogger("test"))
    intent = parser.parse("Please show my drive files")
    assert intent.service == "drive"
    assert intent.action == "list_files"


def test_heuristic_parser_requests_clarification_for_unknown_service(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("GWS_BINARY_PATH", "gws")
    # Clear fallback models to avoid validation errors from user's .env
    # Set to empty string (not delete) to prevent load_dotenv from re-loading from .env
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "")
    monkeypatch.setenv("LLM_FALLBACK_MODEL2", "")
    monkeypatch.setenv("LLM_FALLBACK_MODEL3", "")
    # Clear config cache to ensure environment changes take effect
    AppConfig.clear_cache()
    config = AppConfig.from_env()
    parser = IntentParser(config=config, logger=logging.getLogger("test"))
    intent = parser.parse("Please check my social media posts")
    assert intent.service is None
    assert intent.needs_clarification is True
