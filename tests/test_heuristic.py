import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.config import AppConfig


def test_heuristic_plans_drive_sheet_email(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "recipient@example.test")
    monkeypatch.setenv("GWS_BINARY_PATH", str(tmp_path / "gws"))
    monkeypatch.setenv("MEM0_API_KEY", "")
    monkeypatch.setenv("MEM0_USER_ID", "test-user")

    logger = logging.getLogger("test")
    config = AppConfig.from_env()
    config.use_heuristic_fallback = True
    config.langchain_enabled = False

    system = WorkspaceAgentSystem(config=config, logger=logger)
    email = os.getenv("DEFAULT_RECIPIENT_EMAIL")
    text = f"Search Google Documents for 'Agentic AI - Builders' and convert data to table format and save it and create a Sheet from these and then Send email to '{email}' and append the link of those sheets and also attach as attachment."
    plan = system.plan(text)

    assert plan.tasks
    assert any(task.service == "gmail" and task.action == "send_message" for task in plan.tasks)
