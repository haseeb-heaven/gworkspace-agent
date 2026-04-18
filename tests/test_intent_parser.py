from __future__ import annotations

import logging

from gws_assistant.config import AppConfig
from gws_assistant.intent_parser import IntentParser


def test_heuristic_parser_detects_drive(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
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
    config = AppConfig.from_env()
    parser = IntentParser(config=config, logger=logging.getLogger("test"))
    intent = parser.parse("Please check my social media posts")
    assert intent.service is None
    assert intent.needs_clarification is True
