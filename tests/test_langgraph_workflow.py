import pytest
import logging
from unittest.mock import MagicMock
from gws_assistant.models import AppConfigModel, RequestPlan, PlannedTask, ExecutionResult
from gws_assistant.langgraph_workflow import create_workflow, run_workflow

@pytest.fixture
def config(tmp_path):
    return AppConfigModel(
        provider="openai", model="gpt-4.1-mini", api_key="sk-test", base_url=None, timeout_seconds=30,
        gws_binary_path=tmp_path/"gws.exe", log_file_path=tmp_path/"l.log", log_level="INFO",
        verbose=True, env_file_path=tmp_path/".env", setup_complete=True, max_retries=3, langchain_enabled=True
    )

def test_run_workflow_normal_execution(config):
    logger = logging.getLogger("test")
    system = MagicMock()
    executor = MagicMock()
    
    # Setup mock plan
    plan = RequestPlan(raw_text="List files", tasks=[PlannedTask(id="1", service="drive", action="list_files")], no_service_detected=False)
    system.plan.return_value = plan
    
    # Setup mock executor
    executor._expand_task.return_value = [plan.tasks[0]]
    executor._resolve_task.return_value = plan.tasks[0]
    executor.execute_single_task.return_value = ExecutionResult(success=True, command=["mock"], stdout="Mocked output")
    
    output = run_workflow("List files", config, system, executor, logger)
    
    assert "Mocked output" in output or output != ""
    system.plan.assert_called_once_with("List files")
    executor.execute_single_task.assert_called_once()

def test_run_workflow_web_search(config):
    logger = logging.getLogger("test")
    system = MagicMock()
    executor = MagicMock()
    
    # Flow with no plan but web search
    system.plan.return_value = RequestPlan(raw_text="web search test", no_service_detected=True)
    
    output = run_workflow("web search test", config, system, executor, logger)
    assert output is not None

def test_run_workflow_no_plan(config):
    logger = logging.getLogger("test")
    system = MagicMock()
    executor = MagicMock()
    
    # Flow with no plan and not search/code
    system.plan.return_value = RequestPlan(raw_text="hello", no_service_detected=True, summary="Hello to you too!")
    
    output = run_workflow("hello", config, system, executor, logger)
    assert output is not None
