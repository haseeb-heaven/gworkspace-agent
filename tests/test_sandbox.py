import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.execution import PlanExecutor
from gws_assistant.models import AppConfigModel, PlannedTask
from gws_assistant.planner import CommandPlanner


@pytest.fixture
def mock_config():
    return AppConfigModel(
        provider="openrouter",
        model="meta-llama/llama-3.3-70b-instruct:free",
        api_key="fake-key",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=30,
        gws_binary_path=Path("gws"),
        log_file_path=Path("logs/test.log"),
        log_level="INFO",
        verbose=False,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        sandbox_enabled=True,
        read_only_mode=False,
    )


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner.run.return_value = MagicMock(success=True, stdout="{}", output={})
    return runner


@pytest.fixture
def executor(mock_config, mock_runner):
    return PlanExecutor(
        planner=CommandPlanner(), runner=mock_runner, logger=logging.getLogger("test"), config=mock_config
    )


@pytest.mark.drive
def test_readonly_mode_blocks_delete(mock_config, mock_runner, executor):
    mock_config.read_only_mode = True

    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "file123"})
    result = executor.execute_single_task(task, {})

    assert result.success is False
    assert "blocked" in result.error
    mock_runner.run.assert_not_called()


@pytest.mark.drive
def test_sandbox_mode_declined(mock_config, mock_runner, executor):
    mock_config.read_only_mode = False
    mock_config.sandbox_enabled = True

    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "file123"})

    with patch("builtins.input", return_value="n"):
        result = executor.execute_single_task(task, {})

    assert result.success is False
    assert "aborted" in result.error
    mock_runner.run.assert_not_called()


@pytest.mark.drive
def test_sandbox_mode_accepted(mock_config, mock_runner, executor):
    mock_config.read_only_mode = False
    mock_config.sandbox_enabled = True

    task = PlannedTask(id="1", service="drive", action="delete_file", parameters={"file_id": "file123"})

    with patch("builtins.input", return_value="y"):
        result = executor.execute_single_task(task, {})

    assert result.success is True
    mock_runner.run.assert_called_once()


@pytest.mark.drive
def test_write_action_blocked_in_readonly(mock_config, mock_runner, executor):
    mock_config.read_only_mode = True

    task = PlannedTask(id="1", service="sheets", action="create_spreadsheet", parameters={"title": "Test"})
    result = executor.execute_single_task(task, {})

    assert result.success is False
    assert "blocked" in result.error
    mock_runner.run.assert_not_called()
