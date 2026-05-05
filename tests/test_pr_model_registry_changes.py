"""Tests for PR changes in gws_assistant/model_registry.py.

Covers:
- "groq/llama-3.1-70b-versatile" was REMOVED from TOOL_CAPABLE_MODELS
- All remaining models in the registry still pass validation
- validate_tool_model still accepts known-good models and rejects unknowns
"""
from __future__ import annotations

import pytest

from gws_assistant.model_registry import TOOL_CAPABLE_MODELS, validate_tool_model

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# groq/llama-3.1-70b-versatile removed (PR change)
# ---------------------------------------------------------------------------

class TestRemovedModel:
    def test_groq_llama_3_1_70b_not_in_registry(self):
        """PR explicitly removed groq/llama-3.1-70b-versatile from the allowlist."""
        assert "groq/llama-3.1-70b-versatile" not in TOOL_CAPABLE_MODELS

    def test_groq_llama_3_1_70b_raises_on_validation(self):
        """Validation should fail for the removed model."""
        with pytest.raises(ValueError, match="tool-capable model allowlist"):
            validate_tool_model("groq/llama-3.1-70b-versatile")

    def test_groq_llama_3_3_70b_still_present(self):
        """The 3.3 variant should still be in the registry."""
        assert "groq/llama-3.3-70b-versatile" in TOOL_CAPABLE_MODELS

    def test_groq_llama_3_3_70b_passes_validation(self):
        validate_tool_model("groq/llama-3.3-70b-versatile")


# ---------------------------------------------------------------------------
# Registry still contains key models that were NOT removed
# ---------------------------------------------------------------------------

class TestRegistryIntegrity:
    def test_openrouter_groq_llama_3_1_70b_via_openrouter_still_present(self):
        """openrouter-routed version of llama-3.1-70b is still allowed."""
        assert "openrouter/groq/llama-3.1-70b-versatile" in TOOL_CAPABLE_MODELS

    def test_groq_llama_3_1_8b_still_present(self):
        assert "groq/llama-3.1-8b-instant" in TOOL_CAPABLE_MODELS

    def test_cerebras_models_still_present(self):
        assert "cerebras/llama3.1-70b" in TOOL_CAPABLE_MODELS
        assert "cerebras/llama3.1-8b" in TOOL_CAPABLE_MODELS

    def test_all_remaining_registry_models_pass_validation(self):
        """Regression: all models currently in the registry must pass validation."""
        for model in TOOL_CAPABLE_MODELS:
            validate_tool_model(model)  # must not raise

    def test_registry_is_non_empty(self):
        assert len(TOOL_CAPABLE_MODELS) > 0


# ---------------------------------------------------------------------------
# Boundary / negative tests
# ---------------------------------------------------------------------------

class TestValidateToolModelBoundary:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            validate_tool_model("")

    def test_whitespace_string_raises(self):
        with pytest.raises(ValueError):
            validate_tool_model("   ")

    def test_mock_model_gpt_41_mini_passes(self):
        """Test-only mock model should still be allowed."""
        validate_tool_model("gpt-4.1-mini")

    def test_mock_model_openrouter_free_passes(self):
        validate_tool_model("openrouter/free")

    def test_model_with_leading_trailing_whitespace_passes_if_in_registry(self):
        """validate_tool_model strips whitespace before checking."""
        # Pick a known-good model and add whitespace
        validate_tool_model("  groq/llama-3.3-70b-versatile  ")

    def test_partial_model_name_raises(self):
        """Partial match should not be enough."""
        with pytest.raises(ValueError):
            validate_tool_model("groq/llama")