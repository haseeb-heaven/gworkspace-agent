import os
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from src.gws_assistant.gws_runner import GWSRunner
from src.gws_assistant.models import AppConfigModel

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def config():
    return AppConfigModel(
        provider="openai",
        model="gpt-4",
        api_key="test_key",
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=Path("gws"),
        log_file_path=Path("logs/test.log"),
        log_level="INFO",
        verbose=True,
        env_file_path=Path(".env"),
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        gws_max_retries=3
    )

def test_key_rotation_on_429(mock_logger, config):
    # Set up multiple keys
    os.environ["GWS_API_KEYS"] = "key1,key2,key3"
    
    runner = GWSRunner(gws_binary_path=Path("gws"), logger=mock_logger, config=config)
    
    # We expect rotate_key to be called and change GWS_API_KEY in environment
    # Initially we can set it to key1
    os.environ["GWS_API_KEY"] = "key1"
    
    with patch("subprocess.run") as mock_run:
        # First call returns 429, second call returns 0
        mock_run.side_effect = [
            MagicMock(returncode=429, stdout="", stderr="Rate limit exceeded"),
            MagicMock(returncode=0, stdout="Success", stderr="")
        ]
        
        # We need to mock time.sleep to avoid waiting in tests
        with patch("time.sleep"):
            result = runner.run_with_retry(["some", "command"])
            
            assert result.success is True
            assert result.stdout == "Success"
            assert os.environ["GWS_API_KEY"] == "key2"
            assert mock_run.call_count == 2
            mock_logger.warning.assert_any_call(
                "Rate limit (429) detected. Rotating API key and retrying..."
            )

def test_rotate_key_method(mock_logger, config):
    os.environ["GWS_API_KEYS"] = "key1,key2,key3"
    os.environ["GWS_API_KEY"] = "key1"
    
    runner = GWSRunner(gws_binary_path=Path("gws"), logger=mock_logger, config=config)
    
    runner.rotate_key()
    assert os.environ["GWS_API_KEY"] == "key2"
    
    runner.rotate_key()
    assert os.environ["GWS_API_KEY"] == "key3"
    
    runner.rotate_key()
    assert os.environ["GWS_API_KEY"] == "key1"
