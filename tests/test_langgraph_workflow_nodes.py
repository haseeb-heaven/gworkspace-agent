"""Unit tests for langgraph_workflow nodes."""
from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock, patch

from gws_assistant.langgraph_workflow import create_workflow, WorkflowNodes
from gws_assistant.models import PlannedTask, RequestPlan, StructuredToolResult, ReflectionDecision, TaskExecution


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.verbose = True
    config.max_retries = 3
    config.max_replans = 1
    return config


@pytest.fixture
def mock_system():
    return MagicMock()


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor._expand_task.side_effect = lambda t, c: [t]
    executor._resolve_task.side_effect = lambda t, c: t
    return executor


@pytest.fixture
def logger():
    return logging.getLogger("test_workflow")


@pytest.fixture
def nodes(mock_config, mock_system, mock_executor, logger):
    return WorkflowNodes(mock_config, mock_system, mock_executor, logger)


class TestWorkflowNodes:
    def test_validate_node_empty_plan(self, nodes):
        state = {"plan": None}
        result = nodes.validate_node(state)
        assert result["error"] == "No plan to validate."

    def test_validate_node_missing_action(self, nodes):
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="")])
        state = {"plan": plan}
        result = nodes.validate_node(state)
        assert "has no action" in result["error"]

    def test_validate_node_valid(self, nodes):
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="send")])
        state = {"plan": plan}
        result = nodes.validate_node(state)
        assert result["error"] is None

    def test_update_context_node_increment(self, nodes):
        state = {"current_task_index": 0, "error": None}
        result = nodes.update_context_node(state)
        assert result["current_task_index"] == 1
        assert result["current_attempt"] == 0

    def test_execute_task_node_no_tasks(self, nodes):
        state = {"plan": None, "current_task_index": 0}
        result = nodes.execute_task_node(state)
        assert result["error"] == "No tasks to execute."

    def test_execute_task_node_success(self, nodes, mock_executor):
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="send", parameters={})])
        state = {"plan": plan, "current_task_index": 0, "context": {}, "executions": []}
        
        mock_res = MagicMock()
        mock_res.success = True
        mock_res.output = {"parsed_payload": {"id": "m123"}}
        mock_res.to_structured_result.return_value = StructuredToolResult(success=True, output={"id": "m123"}, error=None)
        mock_executor.execute_single_task.return_value = mock_res
        
        result = nodes.execute_task_node(state)
        assert result["error"] is None
        assert len(result["executions"]) == 1
        assert result["context"]["task_results"]["task-1"] == {"id": "m123"}

    def test_reflect_node_replan(self, nodes, mock_executor, mock_config):
        mock_config.max_replans = 1
        mock_executor.reflect_on_error.return_value = (ReflectionDecision(action="replan", reason="Need new plan"), False)
        
        state = {"error": "failed", "current_attempt": 1, "context": {"replan_count": 0}, "plan": MagicMock()}
        result = nodes.reflect_node(state)
        
        assert result["reflection"].action == "replan"

    def test_format_output_node_success(self, nodes):
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="s", action="a")])
        mock_res = MagicMock()
        mock_res.success = True
        executions = [TaskExecution(task=plan.tasks[0], result=mock_res)]
        
        state = {"plan": plan, "executions": executions, "context": {}}
        result = nodes.format_output_node(state)
        assert "final_output" in result
