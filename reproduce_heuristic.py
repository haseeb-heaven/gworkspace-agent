import logging
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.config import AppConfig
from gws_assistant.planner import CommandPlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")
config = AppConfig.from_env()
config.use_heuristic_fallback = True
config.langchain_enabled = False

system = WorkspaceAgentSystem(config=config, logger=logger)
planner = CommandPlanner()

def test_export_heuristic():
    text = "drive export 1AbCdEFg123"
    plan = system.plan(text)
    print(f"Plan summary: {plan.summary}")
    for task in plan.tasks:
        print(f"Task: {task.service}.{task.action}, Parameters: {task.parameters}")
        try:
            cmd = planner.build_command(task.service, task.action, task.parameters)
            print(f"  Command: {cmd}")
        except Exception as e:
            print(f"  FAILED to build command: {e}")

if __name__ == "__main__":
    test_export_heuristic()
