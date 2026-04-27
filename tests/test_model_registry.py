import pytest
from gws_assistant.model_registry import validate_tool_model, TOOL_CAPABLE_MODELS

pytestmark = pytest.mark.llm

def test_valid_model_passes():
    validate_tool_model("openrouter/nvidia/nemotron-super-49b-v1:free")

def test_invalid_model_raises():
    with pytest.raises(ValueError, match="tool-capable model allowlist"):
        validate_tool_model("openai/gpt-4o-mini", "LLM_MODEL")

def test_all_registry_models_pass_validation():
    for model in TOOL_CAPABLE_MODELS:
        validate_tool_model(model)  # must not raise

def test_fallback_filters_non_tool_models():
    candidates = [
        "openrouter/nvidia/nemotron-super-49b-v1:free",  # valid
        "openai/gpt-3.5-turbo",                           # invalid
        "anthropic/claude-3-opus",                        # invalid
    ]
    safe = [m for m in candidates if m in TOOL_CAPABLE_MODELS]
    assert safe == ["openrouter/nvidia/nemotron-super-49b-v1:free"]
