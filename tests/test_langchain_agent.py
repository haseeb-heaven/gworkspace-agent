import pytest
import logging
from unittest.mock import MagicMock
from gws_assistant.models import AppConfigModel
from gws_assistant.langchain_agent import plan_with_langchain, create_agent

@pytest.fixture
def config_with_key(tmp_path):
    return AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key="sk-test",
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=tmp_path / "gws.exe",
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        verbose=True,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
    )

def test_create_agent_no_key(tmp_path):
    logger = logging.getLogger("test")
    config = AppConfigModel(
        provider="openai", model="gpt-4.1-mini", api_key=None, base_url=None, timeout_seconds=30,
        gws_binary_path=tmp_path/"gws.exe", log_file_path=tmp_path/"l.log", log_level="INFO",
        verbose=True, env_file_path=tmp_path/".env", setup_complete=True, max_retries=3, langchain_enabled=True
    )
    assert create_agent(config, logger) is None

def test_plan_with_langchain(mocker, config_with_key):
    logger = logging.getLogger("test")
    mock_model = MagicMock()
    mock_chain = MagicMock()
    
    # Mock prompt | model.with_structured_output()
    mock_model.with_structured_output.return_value = mock_chain
    mocker.patch("gws_assistant.langchain_agent.create_agent", return_value=mock_model)
    mocker.patch("langchain_core.prompts.ChatPromptTemplate.from_messages", return_value=MagicMock(__or__=lambda self, other: mock_chain))
    
    mock_plan = MagicMock()
    mock_plan.summary = "Test Output"
    mock_plan.confidence = 0.0
    mock_plan.tasks = ["task1"]
    mock_chain.invoke.return_value = mock_plan
    
    plan = plan_with_langchain("test request", config_with_key, logger)
    assert plan is mock_plan
    assert plan.confidence == 0.9 # Should be updated by hook
