import pytest
import os
from gws_assistant.config import AppConfig

@pytest.fixture(autouse=True)
def mock_load_dotenv(monkeypatch):
    import gws_assistant.config
    monkeypatch.setattr(gws_assistant.config, "load_dotenv", lambda **kwargs: None)

def test_config_raises_value_error_if_recipient_email_missing(monkeypatch):
    """Test that ValueError is raised if DEFAULT_RECIPIENT_EMAIL is missing."""
    monkeypatch.setenv("GWS_BINARY_PATH", "gws")
    monkeypatch.delenv("DEFAULT_RECIPIENT_EMAIL", raising=False)
    # Ensure other required env vars are present if any (let's assume only this one for now)
    with pytest.raises(ValueError, match="DEFAULT_RECIPIENT_EMAIL must be set in .env"):
        AppConfig.from_env()

def test_config_accepts_recipient_email_if_present(monkeypatch):
    """Test that config loads correctly if DEFAULT_RECIPIENT_EMAIL is present."""
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("GWS_BINARY_PATH", "gws")
    # Mock other things to avoid errors
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = AppConfig.from_env()
    assert config.default_recipient_email == "test@example.com"

def test_config_raises_value_error_if_gws_binary_missing(monkeypatch):
    """Test that ValueError is raised if GWS_BINARY_PATH is missing."""
    monkeypatch.setenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.delenv("GWS_BINARY_PATH", raising=False)
    with pytest.raises(ValueError, match="GWS_BINARY_PATH must be set in .env"):
        AppConfig.from_env()
