from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.exceptions import SafetyBlockedError, SafetyConfirmationRequired
from gws_assistant.execution.executor import PlanExecutor
from gws_assistant.models import PlannedTask, RequestPlan


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api_key = "test-key"
    config.default_recipient_email = "test@example.com"
    config.force_dangerous = False
    config.dry_run = False
    config.no_confirm = False
    config.is_telegram = False
    config.read_only_mode = False
    config.sandbox_enabled = False
    config.langchain_enabled = True
    return config


@pytest.fixture
def mock_logger():
    return MagicMock()


def test_plan_safety_block_bulk(mock_config, mock_logger):
    agent = WorkspaceAgentSystem(mock_config, mock_logger)

    # Plan with bulk keyword
    plan = RequestPlan(
        raw_text="Delete all files in my drive",
        tasks=[PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "123"})],
    )

    with patch("gws_assistant.agent_system.plan_with_langchain", return_value=plan):
        with pytest.raises(SafetyBlockedError, match="Plan contains bulk destruction keywords"):
            agent.plan("Delete all files in my drive")


def test_plan_safety_block_too_many_destructive(mock_config, mock_logger):
    agent = WorkspaceAgentSystem(mock_config, mock_logger)

    tasks = [
        PlannedTask(id=str(i), service="drive", action="delete_file", parameters={"file_id": str(i)}) for i in range(5)
    ]
    plan = RequestPlan(raw_text="Delete some files", tasks=tasks)

    with patch("gws_assistant.agent_system.plan_with_langchain", return_value=plan):
        with pytest.raises(SafetyBlockedError, match="contains 5 destructive actions"):
            agent.plan("Delete some files")


def test_executor_safety_confirmation_cli(mock_config, mock_logger):
    executor = PlanExecutor(planner=MagicMock(), runner=MagicMock(), config=mock_config, logger=mock_logger)
    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "123"})

    with patch("builtins.input", return_value="n"):
        result = executor.execute_single_task(task, {})
        assert result.success is False
        assert "User aborted" in result.error


def test_executor_safety_confirmation_telegram(mock_config, mock_logger):
    mock_config.is_telegram = True
    executor = PlanExecutor(planner=MagicMock(), runner=MagicMock(), config=mock_config, logger=mock_logger)
    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "123"})

    with pytest.raises(SafetyConfirmationRequired) as excinfo:
        executor.execute_single_task(task, {})

    assert "Are you sure you want to delete_file" in str(excinfo.value)
    assert excinfo.value.action_name == "drive.delete_file"


def test_executor_dry_run(mock_config, mock_logger):
    mock_config.dry_run = True
    executor = PlanExecutor(planner=MagicMock(), runner=MagicMock(), config=mock_config, logger=mock_logger)
    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "123"})

    result = executor.execute_single_task(task, {})
    assert result.success is True
    assert "Dry-run mode active" in result.output["message"]


def test_plan_safety_audit_does_not_log_raw_text(tmp_path):
    plan = RequestPlan(
        raw_text="Delete all files and email alice@example.com secret-token",
        tasks=[PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "123"})],
    )
    log_path = tmp_path / "audit.log"

    with patch("gws_assistant.safety_guard.SafetyGuard._get_audit_log_path", return_value=log_path):
        with pytest.raises(SafetyBlockedError):
            from gws_assistant.safety_guard import SafetyGuard
            SafetyGuard.check_plan(plan)

    log_text = log_path.read_text(encoding="utf-8")
    assert "alice@example.com" not in log_text
    assert "secret-token" not in log_text


def test_confirmation_required_details_are_sanitized(mock_config, mock_logger):
    mock_config.is_telegram = True
    executor = PlanExecutor(planner=MagicMock(), runner=MagicMock(), config=mock_config, logger=mock_logger)
    task = PlannedTask(
        id="1",
        service="drive",
        action="delete_file",
        parameters={"file_id": "123", "body": "secret body", "email": "alice@example.com"},
    )

    with pytest.raises(SafetyConfirmationRequired) as excinfo:
        executor.execute_single_task(task, {})

    assert "secret body" not in excinfo.value.details
    assert "alice@example.com" not in excinfo.value.details
