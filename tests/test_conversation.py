from __future__ import annotations

import logging

from gws_assistant.config import AppConfig
from gws_assistant.conversation import ConversationEngine
from gws_assistant.intent_parser import IntentParser
from gws_assistant.planner import CommandPlanner


def test_conversation_requires_service_clarification(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    config = AppConfig.from_env()
    parser = IntentParser(config=config, logger=logging.getLogger("test"))
    engine = ConversationEngine(parser=parser, planner=CommandPlanner(), logger=logging.getLogger("test"))
    intent = engine.parse_user_request("hello there")
    assert engine.needs_service_clarification(intent) is True
