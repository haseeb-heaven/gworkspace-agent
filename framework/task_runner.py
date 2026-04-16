import time

import pytest

from .cli_runner import GWSCLIRunner
from .logger import setup_framework_logger
from .validator import OutputValidator

logger = setup_framework_logger("task_runner")

class TaskRunner:
    def __init__(self):
        self.runner = GWSCLIRunner()
        self.validator = OutputValidator()

    def execute_and_validate(self, task: str, expected_texts: list[str]) -> bool:
        logger.info(f"Executing task: {task}")
        time.sleep(2)  # Rate limiting
        result = self.runner.run_task(task)

        # Check for environment auth failures first
        if "missing field `client_id`" in result.stderr or "Authentication failed" in result.stderr:
            logger.warning("Auth not configured locally, skipping test to maintain CI progression")
            pytest.skip("GWS Client Secret not configured. Skipping active side-effect validation.")

        if not self.validator.validate_success(result):
            return False

        for expected in expected_texts:
            if not self.validator.validate_output_contains(result, expected):
                return False

        logger.info("Task validated successfully")
        return True
