from gws_assistant.config import AppConfig


def test_config_is_singleton():
    """
    Test that AppConfig.from_env() returns a singleton instance.
    Currently, this test is expected to FAIL because from_env() returns a new instance every time.
    """
    config1 = AppConfig.from_env()
    config2 = AppConfig.from_env()

    assert config1 is config2, "AppConfig.from_env() should return the same instance (singleton)"

def test_singleton_preserves_state():
    """
    Test that state mutations (like key rotation) are preserved across calls.
    """
    config1 = AppConfig.from_env()
    # Mock some keys for rotation
    config1.llm_api_keys = ["key1", "key2", "key3"]
    config1.api_key = "key1"
    config1.current_key_idx = 0

    # Rotate in config1
    config1.rotate_api_key()
    assert config1.current_key_idx == 1
    assert config1.api_key == "key2"

    # Get config again
    config2 = AppConfig.from_env()
    assert config2.current_key_idx == 1, "State mutation should be preserved in the singleton"
    assert config2.api_key == "key2"
