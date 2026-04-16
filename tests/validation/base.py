import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from gws_assistant.config import AppConfig
from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.logging_utils import setup_logging
from gws_assistant.planner import CommandPlanner


class SimplePlanner:
    def build_command(self, service, action, params):
        return CommandPlanner().build_command(service, action, params)

def get_executor():
    config = AppConfig.from_env()
    logger = setup_logging(config)
    # Correct path to gws.exe in project root
    gws_path = Path(__file__).resolve().parent.parent.parent / "gws.exe"
    runner = GWSRunner(gws_binary_path=gws_path, logger=logger, config=config)
    # Ensure keyring backend is set to file to avoid secure storage errors
    os.environ["GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND"] = "file"
    return PlanExecutor(planner=SimplePlanner(), runner=runner, config=config)

def create_task(service, action, parameters):
    return type('Task', (), {'service': service, 'action': action, 'parameters': parameters})
