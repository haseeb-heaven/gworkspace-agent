import json
from unittest.mock import MagicMock, patch

import pytest

from gws_assistant.execution.executor import PlanExecutor
from gws_assistant.models import ExecutionResult, PlannedTask
from gws_assistant.planner import CommandPlanner


class TestKeepCRUD:
    @pytest.fixture
    def planner(self):
        return CommandPlanner()

    @pytest.fixture
    def runner(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, planner, runner):
        return PlanExecutor(planner=planner, runner=runner)

    def test_planner_builds_keep_commands(self, planner):
        # Create
        args = planner.build_command("keep", "create_note", {"title": "T1", "body": "B1"})
        assert args == [
            "keep",
            "notes",
            "create",
            "--json",
            json.dumps({"title": "T1", "body": {"text": {"text": "B1"}}}),
        ]

        # Get
        args = planner.build_command("keep", "get_note", {"name": "notes/123"})
        assert args == ["keep", "notes", "get", "--params", json.dumps({"name": "notes/123"})]

        # Delete
        args = planner.build_command("keep", "delete_note", {"name": "notes/123"})
        assert args == ["keep", "notes", "delete", "--params", json.dumps({"name": "notes/123"})]

        # List
        args = planner.build_command("keep", "list_notes", {"page_size": 5})
        assert args == ["keep", "notes", "list", "--params", json.dumps({"pageSize": 5})]

    def test_keep_lifecycle_execution(self, executor, runner):
        # 1. Create Note Task
        create_task = PlannedTask(
            id="t1", service="keep", action="create_note", parameters={"title": "Life", "body": "Cycle"}
        )

        # Mock create response
        runner.run.side_effect = [
            # Create call
            ExecutionResult(
                success=True, command=[], stdout=json.dumps({"name": "notes/created12345678", "title": "Life"})
            ),
            # Triple-check calls (3 times get_note)
            ExecutionResult(success=True, command=[], stdout=json.dumps({"name": "notes/created12345678"})),
            ExecutionResult(success=True, command=[], stdout=json.dumps({"name": "notes/created12345678"})),
            ExecutionResult(success=True, command=[], stdout=json.dumps({"name": "notes/created12345678"})),
            # List call
            ExecutionResult(
                success=True, command=[], stdout=json.dumps({"notes": [{"name": "notes/created12345678"}]})
            ),
            # Delete call
            ExecutionResult(success=True, command=[], stdout=json.dumps({"success": True})),
        ]

        # Execute create
        result = executor.execute_single_task(create_task, {})
        assert result.success
        assert result.output["name"] == "notes/created12345678"
        # Verify Triple-Check was called (1 create + 3 get)
        assert runner.run.call_count == 4

        # 2. List Notes Task
        list_task = PlannedTask(id="t2", service="keep", action="list_notes", parameters={})
        result = executor.execute_single_task(list_task, {})
        assert result.success
        assert len(result.output["notes"]) == 1

        # 3. Delete Note Task
        delete_task = PlannedTask(
            id="t3", service="keep", action="delete_note", parameters={"name": "notes/created12345678"}
        )
        result = executor.execute_single_task(delete_task, {})
        assert result.success

    @patch("time.sleep", return_value=None)  # Fast triple check
    def test_create_note_triple_check_fail(self, mock_sleep, executor, runner):
        create_task = PlannedTask(id="t1", service="keep", action="create_note", parameters={"title": "F", "body": "B"})

        runner.run.side_effect = [
            # Create success
            ExecutionResult(success=True, command=[], stdout=json.dumps({"name": "notes/fail123456789", "title": "F"})),
            # First Triple-check fails
            ExecutionResult(success=False, command=[], error="Not found yet"),
        ]

        result = executor.execute_single_task(create_task, {})
        assert not result.success
        assert "Consistency check failed" in result.error
