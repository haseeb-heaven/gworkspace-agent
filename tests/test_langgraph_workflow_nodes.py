"""Unit tests for langgraph_workflow nodes."""
from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock

from gws_assistant.langgraph_workflow import create_workflow
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
def workflow(mock_config, mock_system, mock_executor, logger):
    return create_workflow(mock_config, mock_system, mock_executor, logger)


class TestWorkflowNodes:
    def test_validate_node_empty_plan(self, workflow):
        validate_node = workflow.nodes["validate_node"]
        state = {"plan": None}
        result = validate_node(state)
        assert result["error"] == "No plan to validate."

    def test_validate_node_missing_action(self, workflow):
        validate_node = workflow.nodes["validate_node"]
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="")])
        state = {"plan": plan}
        result = validate_node(state)
        assert "has no action" in result["error"]

    def test_validate_node_valid(self, workflow):
        validate_node = workflow.nodes["validate_node"]
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="send")])
        state = {"plan": plan}
        result = validate_node(state)
        assert result["error"] is None

    def test_update_context_node_increment(self, workflow):
        update_node = workflow.nodes["update_context_node"]
        state = {"current_task_index": 0, "error": None}
        result = update_node(state)
        assert result["current_task_index"] == 1
        assert result["current_attempt"] == 0

    def test_update_context_node_abort(self, workflow):
        update_node = workflow.nodes["update_context_node"]
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="s", action="a"), PlannedTask(id="2", service="s", action="a")])
        state = {"current_task_index": 0, "abort_plan": True, "plan": plan}
        result = update_node(state)
        assert result["current_task_index"] == 2

    def test_normalize_workspace_result_with_helper(self, workflow):
        # We can't easily test internal helpers unless we expose them or test via nodes.
        # But we can test execute_task_node which uses it.
        pass

    def test_execute_task_node_no_tasks(self, workflow):
        execute_node = workflow.nodes["execute_task_node"]
        state = {"plan": None, "current_task_index": 0}
        result = execute_node(state)
        assert result["error"] == "No tasks to execute."

    def test_execute_task_node_success(self, workflow, mock_executor):
        execute_node = workflow.nodes["execute_task_node"]
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="gmail", action="send", parameters={})])
        state = {"plan": plan, "current_task_index": 0, "context": {}, "executions": []}
        
        mock_res = MagicMock()
        mock_res.success = True
        mock_res.output = {"parsed_payload": {"id": "m123"}}
        mock_res.to_structured_result.return_value = StructuredToolResult(success=True, output={"id": "m123"}, error=None)
        mock_executor.execute_single_task.return_value = mock_res
        
        result = execute_node(state)
        assert result["error"] is None
        assert len(result["executions"]) == 1
        assert result["context"]["task_results"]["task-1"] == {"id": "m123"}


    def test_reflect_node_replan(self, workflow, mock_executor, mock_config):
        reflect_node = workflow.nodes["reflect_node"]
        mock_config.max_replans = 1
        mock_executor.reflect_on_error.return_value = (ReflectionDecision(action="replan", reason="Need new plan"), False)
        
        state = {"error": "failed", "current_attempt": 1, "context": {"replan_count": 0}, "plan": MagicMock()}
        result = reflect_node(state)
        
        assert result["reflection"].action == "replan"
        assert result["context"]["replan_count"] == 1
        assert result["current_task_index"] == 0


    def test_format_output_node_success(self, workflow):
        format_node = workflow.nodes["format_output_node"]
        plan = RequestPlan(raw_text="test", tasks=[PlannedTask(id="1", service="s", action="a")])
        mock_res = MagicMock()
        mock_res.success = True
        executions = [TaskExecution(task=plan.tasks[0], result=mock_res)]
        
        state = {"plan": plan, "executions": executions, "context": {}}
        result = format_node(state)
        assert "final_output" in result
        assert result["final_output"] != "No result produced."


    def test_web_search_node_success(self, workflow):
        # We need to mock web_search_tool which is imported in langgraph_workflow
        with patch("gws_assistant.langgraph_workflow.web_search_tool.invoke") as mock_search:
            mock_search.return_value = {"results": [{"title": "T", "url": "U", "snippet": "S"}]}
            search_node = workflow.nodes["web_search_node"]
            state = {"user_text": "search query", "context": {}}
            result = search_node(state)
            assert result["last_result"].success is True
            assert result["context"]["search_summary_count"] == 1


    def test_code_execution_node_disabled(self, workflow, mock_config):
        mock_config.code_execution_enabled = False
        code_node = workflow.nodes["code_execution_node"]
        state = {"context": {"generated_code": "print(1)"}}
        result = code_node(state)
        assert "disabled" in result["error"]
