from __future__ import annotations

import logging

from gws_assistant.config import AppConfig
from gws_assistant.conversation import ConversationEngine
from gws_assistant.models import Intent
from gws_assistant.planner import CommandPlanner


def test_conversation_requires_service_clarification(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    AppConfig.from_env()
    engine = ConversationEngine(planner=CommandPlanner(), logger=logging.getLogger("test"))
    intent = Intent(raw_text="hello there", service=None, action=None)
    assert engine.needs_service_clarification(intent) is True
