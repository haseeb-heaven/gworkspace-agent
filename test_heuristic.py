import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.config import AppConfig

logger = logging.getLogger("test")
config = AppConfig()
config.use_heuristic_fallback = True
config.langchain_enabled = False # force heuristic

system = WorkspaceAgentSystem(config=config, logger=logger)
import os

email = os.getenv("DEFAULT_RECIPIENT_EMAIL", "user@example.com")
text = f"Search Google Documents for 'Agentic AI - Builders' and convert data to table format and save it and create a Sheet from these and then Send email to '{email}' and append the link of those sheets and also attach as attachment."
plan = system.plan(text)
print(f"Tasks: {len(plan.tasks)}")
print(f"Tasks list: {[t.action for t in plan.tasks]}")

