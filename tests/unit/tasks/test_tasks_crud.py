import json
import pytest
from unittest.mock import MagicMock, patch
from gws_assistant.planner import CommandPlanner
from gws_assistant.execution.executor import PlanExecutor
from gws_assistant.models import RequestPlan, PlannedTask, ExecutionResult

class TestTasksCRUD:
    @pytest.fixture
    def planner(self):
        return CommandPlanner()

    @pytest.fixture
    def runner(self):
        return MagicMock()

    @pytest.fixture
    def executor(self, planner, runner):
        return PlanExecutor(planner=planner, runner=runner)

    def test_planner_builds_tasks_commands(self, planner):
        # Create
        args = planner.build_command("tasks", "create_task", {"title": "Buy milk", "notes": "2% fat"})
        assert args == ["tasks", "tasks", "insert", "--params", json.dumps({"tasklist": "@default"}), "--json", json.dumps({"title": "Buy milk", "notes": "2% fat"})]

        # Get
        args = planner.build_command("tasks", "get_task", {"task_id": "t123"})
        assert args == ["tasks", "tasks", "get", "--params", json.dumps({"tasklist": "@default", "task": "t123"})]

        # Update
        args = planner.build_command("tasks", "update_task", {"task_id": "t123", "status": "completed"})
        assert args == ["tasks", "tasks", "update", "--params", json.dumps({"tasklist": "@default", "task": "t123"}), "--json", json.dumps({"status": "completed"})]

        # Delete
        args = planner.build_command("tasks", "delete_task", {"task_id": "t123"})
        assert args == ["tasks", "tasks", "delete", "--params", json.dumps({"tasklist": "@default", "task": "t123"})]

    def test_tasks_lifecycle_execution(self, executor, runner):
        create_task = PlannedTask(id="t1", service="tasks", action="create_task", parameters={"title": "Test Task"})
        
        runner.run.side_effect = [
            # Create call
            ExecutionResult(success=True, command=[], stdout=json.dumps({"id": "task123", "title": "Test Task"})),
            # Triple-check calls (3 times get_task)
            ExecutionResult(success=True, command=[], stdout=json.dumps({"id": "task123"})),
            ExecutionResult(success=True, command=[], stdout=json.dumps({"id": "task123"})),
            ExecutionResult(success=True, command=[], stdout=json.dumps({"id": "task123"})),
        ]
        
        result = executor.execute_single_task(create_task, {})
        assert result.success
        assert result.output["id"] == "task123"
        assert runner.run.call_count == 4
