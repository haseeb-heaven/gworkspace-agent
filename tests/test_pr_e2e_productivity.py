"""Final sanity and end-to-end validation tests for PR #105."""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.config import AppConfig
from gws_assistant.execution import PlanExecutor
from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import ExecutionResult, PlannedTask, RequestPlan
from gws_assistant.planner import CommandPlanner
from gws_assistant.tools.code_execution import execute_generated_code


from unittest.mock import MagicMock

from gws_assistant.models import AppConfigModel

class FakeRunner(GWSRunner):
    def __init__(self) -> None:
        super().__init__(Path("gws.exe"), logging.getLogger("test"))
        self.commands: list[list[str]] = []

    def run(self, args: list[str], timeout_seconds: int = 90) -> ExecutionResult:
        self.commands.append(args)
        if "gmail" in args and "list" in args:
            return ExecutionResult(
                success=True,
                command=["gws", *args],
                stdout=json.dumps({
                    "messages": [{"id": "m1", "threadId": "t1"}, {"id": "m2", "threadId": "t2"}],
                    "resultSizeEstimate": 2
                }),
            )
        if "gmail" in args and "get" in args:
            msg_id = "m1"
            for i, arg in enumerate(args):
                if arg == "--params":
                    p_data = json.loads(args[i + 1])
                    msg_id = p_data.get("id") or msg_id

            body_text = "Hello, please review the budget." if msg_id == "m1" else "Todo: update docs."
            body_b64 = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("utf-8")

            return ExecutionResult(
                success=True,
                command=["gws", *args],
                stdout=json.dumps({
                    "id": msg_id,
                    "snippet": "Snippet...",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Alice <alice@example.com>"},
                            {"name": "Subject", "value": f"Subject {msg_id}"},
                            {"name": "Date", "value": "2026-05-06"}
                        ],
                        "body": {"data": body_b64}
                    }
                }),
            )
        if "tasks" in args and "create" in args:
            return ExecutionResult(success=True, command=["gws", *args], stdout='{"id": "task-abc"}')
        if "calendar" in args and "insert" in args:
            return ExecutionResult(success=True, command=["gws", *args], stdout='{"id": "evt-abc"}')

        return ExecutionResult(success=True, command=["gws", *args], stdout='{}')


@pytest.fixture
def agent_system(tmp_path):
    config = AppConfigModel(
        provider="openrouter",
        model="openrouter/free",
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        gws_binary_path=Path("gws.exe"),
        log_file_path=tmp_path / "test.log",
        log_level="DEBUG",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        max_replans=1,
        langchain_enabled=True,
        use_heuristic_fallback=True,
        code_execution_enabled=True,
        code_execution_backend="local",
        code_execution_timeout_seconds=5,
        default_recipient_email="test@example.com",
        drive_folder_name="Test Folder",
        llm_api_keys=["sk-test"],
        llm_fallback_models=[],
    )
    return WorkspaceAgentSystem(config=config, logger=logging.getLogger("test"))


def test_gmail_to_productivity_chain_e2e(agent_system, mocker):
    """End-to-end validation of the Gmail -> Productivity chain.

    Verifies:
    1. Heuristic plan generation.
    2. task-3 code execution extracts items.
    3. task-4 fan-out creates individual tasks.
    4. task-5 and task-6 resolve placeholders correctly.
    """
    runner = FakeRunner()
    executor = PlanExecutor(planner=CommandPlanner(), runner=runner, logger=logging.getLogger("test"))

    # Mock Telegram to avoid network calls
    mocker.patch("gws_assistant.tools.telegram.send_telegram", return_value=True)

    prompt = "scan my last 5 emails, extract action items, create Google Tasks for each, and send me a summary on Telegram"
    plan = agent_system.plan(prompt)

    assert plan.source == "heuristic"
    assert len(plan.tasks) >= 4
    assert plan.tasks[0].service == "gmail"
    assert plan.tasks[2].service == "code"
    assert plan.tasks[3].service == "tasks"

    report = executor.execute(plan)
    assert report.success is True, "Execution failed"

    # Verify code task (task-3) produced parsed_value
    code_exec = next(e for e in report.executions if e.task.id == "task-3")
    assert isinstance(code_exec.result.output.get("parsed_value"), list)
    extracted = code_exec.result.output["parsed_value"]
    assert len(extracted) > 0

    # Verify Tasks fan-out (task-4-1, task-4-2, ...)
    task_creations = [e for e in report.executions if e.task.service == "tasks" and e.task.action == "create_task"]
    assert len(task_creations) == len(extracted)
    for i, e in enumerate(task_creations):
        assert e.task.id == f"task-4-{i+1}"
        assert e.task.parameters["title"] == extracted[i]

    # Verify Telegram (task-6) resolution
    telegram_exec = next(e for e in report.executions if e.task.service == "telegram")
    # Placeholder {{task-3.parsed_value}} should be replaced by string representation of the list
    # Use json.dumps to match double-quotes likely used by the resolver/json output
    assert json.dumps(extracted) in telegram_exec.task.parameters["message"]


def test_code_execution_return_stripping_preserves_nested():
    """Confirms top-level return is stripped but nested returns are preserved."""
    code = """
def my_func():
    return "inner"

x = my_func()
return x
"""
    result = execute_generated_code(code)
    assert result["success"] is True
    # The module should finish and 'x' should be "inner"
    assert result["output"].get("x") == "inner"


def test_code_execution_with_open_csv_reader_flow():
    """Validates with-open + csv.DictReader transformation and execution.

    Ensures:
    1. Reads from injected_vars[0].
    2. Preserves alias.
    3. Handles iters.
    """
    code = """
import csv
with open('data.csv', 'r') as f:
    reader = csv.DictReader(f)
    results = []
    for row in reader:
        results.append(row['Category'])
result = results
"""
    # Headers in first row, data in second
    data = [["Category", "Value"], ["A", "10"], ["B", "20"]]
    result = execute_generated_code(code, extra_globals={"injected_vars": [data]})

    assert result["success"] is True, f"Code failed: {result.get('error')}\nCode:\n{result.get('output', {}).get('code')}"
    assert result["output"].get("parsed_value") == ["A", "B"]


def test_telegram_fail_fast_on_unresolved(mocker):
    """Confirm Telegram helper fails fast on unresolved content."""
    from gws_assistant.execution.helpers import HelpersMixin
    from gws_assistant.execution.resolver import _UNRESOLVED_MARKER

    mixin = HelpersMixin()
    mixin.logger = logging.getLogger("test")
    mixin.config = SimpleNamespace(telegram_bot_token="t", telegram_chat_id="c")
    mixin._resolve_placeholders = MagicMock(return_value=_UNRESOLVED_MARKER)

    # Mock transport to ensure it's NOT called
    mock_send = mocker.patch("gws_assistant.tools.telegram.send_telegram")

    task = SimpleNamespace(
        id="task-1",
        service="telegram",
        action="send_message",
        parameters={"message": "{{unresolved}}"}
    )

    res = mixin._handle_telegram_task(task, {})

    assert res.success is False
    assert "unresolved placeholder" in res.error
    mock_send.assert_not_called()

    # Test None resolution
    mixin._resolve_placeholders.return_value = None
    res = mixin._handle_telegram_task(task, {})
    assert res.success is False
    assert "unresolved placeholder" in res.error
    mock_send.assert_not_called()
