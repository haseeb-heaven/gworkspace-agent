import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gws_assistant.config import AppConfig


@pytest.fixture
def mock_env():
    with patch.dict(
        os.environ,
        {
            "GWS_BINARY_PATH": "gws",
            "DEFAULT_RECIPIENT_EMAIL": "test@example.com",
            "SANDBOX_ENABLED": "true",
            "READ_ONLY_MODE": "true",
        },
    ):
        yield


@pytest.mark.drive
def test_config_reads_env_true(mock_env):
    with patch("pathlib.Path.exists", return_value=False):  # Force no .env file
        with patch("gws_assistant.config.load_dotenv"):
            config = AppConfig.from_env()
            assert config.sandbox_enabled is True
            assert config.read_only_mode is True


@pytest.mark.drive
def test_config_reads_env_false(mock_env):
    with patch.dict(os.environ, {"SANDBOX_ENABLED": "false", "READ_ONLY_MODE": "false"}):
        with patch("pathlib.Path.exists", return_value=False):
            with patch("gws_assistant.config.load_dotenv"):
                config = AppConfig.from_env()
                assert config.sandbox_enabled is False
                assert config.read_only_mode is False


@pytest.mark.drive
def test_cli_overrides_env_to_false(mock_env):
    # Env says True, CLI says False
    # Mocking components that _run_application imports locally
    with patch("gws_assistant.cli_app.setup_logging"):
        with patch("gws_assistant.agent_system.WorkspaceAgentSystem"):
            with patch("gws_assistant.gws_runner.GWSRunner") as mock_runner:
                mock_runner.return_value.validate_binary.return_value = True
                with patch("gws_assistant.execution.PlanExecutor"):
                    with patch("gws_assistant.langgraph_workflow.run_workflow", side_effect=KeyboardInterrupt):
                        with patch("gws_assistant.config.AppConfig.from_env") as mock_from_env:
                            from gws_assistant.models import AppConfigModel

                            base_config = AppConfigModel(
                                provider="openrouter",
                                model="m",
                                api_key="k",
                                base_url="b",
                                timeout_seconds=30,
                                gws_binary_path=Path("gws"),
                                log_file_path=Path("l"),
                                log_level="INFO",
                                verbose=False,
                                env_file_path=Path(".env"),
                                setup_complete=True,
                                max_retries=3,
                                langchain_enabled=True,
                                sandbox_enabled=True,
                                read_only_mode=True,
                            )
                            mock_from_env.return_value = base_config

                            from gws_assistant.cli_app import _run_application

                            try:
                                # Pass task="test" to avoid interactive prompt
                                _run_application(sandbox=False, read_only=False, task="test")
                            except KeyboardInterrupt:
                                pass

                            assert base_config.sandbox_enabled is False
                            assert base_config.read_only_mode is False


@pytest.mark.drive
def test_cli_respects_env_if_none(mock_env):
    # Env says True, CLI says None (default)
    with patch("gws_assistant.cli_app.setup_logging"):
        with patch("gws_assistant.agent_system.WorkspaceAgentSystem"):
            with patch("gws_assistant.gws_runner.GWSRunner") as mock_runner:
                mock_runner.return_value.validate_binary.return_value = True
                with patch("gws_assistant.execution.PlanExecutor"):
                    with patch("gws_assistant.langgraph_workflow.run_workflow", side_effect=KeyboardInterrupt):
                        with patch("gws_assistant.config.AppConfig.from_env") as mock_from_env:
                            from gws_assistant.models import AppConfigModel

                            base_config = AppConfigModel(
                                provider="openrouter",
                                model="m",
                                api_key="k",
                                base_url="b",
                                timeout_seconds=30,
                                gws_binary_path=Path("gws"),
                                log_file_path=Path("l"),
                                log_level="INFO",
                                verbose=False,
                                env_file_path=Path(".env"),
                                setup_complete=True,
                                max_retries=3,
                                langchain_enabled=True,
                                sandbox_enabled=True,
                                read_only_mode=True,
                            )
                            mock_from_env.return_value = base_config

                            from gws_assistant.cli_app import _run_application

                            try:
                                # Pass task="test" to avoid interactive prompt
                                _run_application(sandbox=None, read_only=None, task="test")
                            except KeyboardInterrupt:
                                pass

                            assert base_config.sandbox_enabled is True
                            assert base_config.read_only_mode is True
