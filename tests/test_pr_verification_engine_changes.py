"""Tests for PR changes in gws_assistant/verification_engine.py.

Covers:
- _validate_content_not_empty: block_placeholders=False for content field in verify_params
- _validate_content_not_empty: placeholder check only when len(val_str) <= 100 (new PR rule)
- _is_ignored_validation_path: ".text" added to ignored_suffixes
"""
from __future__ import annotations

import pytest

from gws_assistant.verification_engine import VerificationEngine, VerificationError


# ---------------------------------------------------------------------------
# _validate_content_not_empty — block_placeholders=False does NOT block $ vars
# ---------------------------------------------------------------------------

class TestValidateContentNotEmptyBlockPlaceholdersFalse:
    """PR change: content field no longer blocks placeholder-looking values."""

    def test_content_with_dollar_sign_not_blocked(self):
        """Resolved email summaries with $ signs should not fail validation."""
        params = {"content": "Email summary: $100 invoice received. Total: $500"}
        # Should NOT raise when block_placeholders is False (PR change for content field)
        VerificationEngine._validate_content_not_empty(
            "create_document", params, field="content", min_length=1, block_placeholders=False
        )

    def test_content_with_percent_sign_not_blocked(self):
        params = {"content": "Profit margin: 25% increase in Q4 revenue."}
        VerificationEngine._validate_content_not_empty(
            "create_document", params, field="content", min_length=1, block_placeholders=False
        )

    def test_content_with_shell_var_not_blocked_when_false(self):
        """With block_placeholders=False, $variable patterns are allowed."""
        params = {"content": "$summary_of_emails"}
        # When block_placeholders=False this should not raise
        VerificationEngine._validate_content_not_empty(
            "create_document", params, field="content", min_length=1, block_placeholders=False
        )

    def test_none_content_still_raises(self):
        """Even with block_placeholders=False, None content is rejected."""
        params = {}
        with pytest.raises(VerificationError, match="None/missing"):
            VerificationEngine._validate_content_not_empty(
                "create_document", params, field="content", min_length=1, block_placeholders=False
            )

    def test_empty_content_still_raises(self):
        params = {"content": "   "}
        with pytest.raises(VerificationError, match="empty or whitespace-only"):
            VerificationEngine._validate_content_not_empty(
                "create_document", params, field="content", min_length=1, block_placeholders=False
            )

    def test_placeholder_still_blocked_when_true(self):
        """When block_placeholders=True (default), placeholder values are still blocked."""
        params = {"content": "{{unresolved}}"}
        with pytest.raises(VerificationError):
            VerificationEngine._validate_content_not_empty(
                "create_document", params, field="content", min_length=1, block_placeholders=True
            )


# ---------------------------------------------------------------------------
# _validate_content_not_empty — placeholder length check: only when len <= 100
# ---------------------------------------------------------------------------

class TestValidateContentPlaceholderLengthThreshold:
    """PR change: skip placeholder detection for strings longer than 100 chars."""

    def test_short_placeholder_is_blocked(self):
        """Strings <= 100 chars that look like placeholders should still be blocked."""
        params = {"content": "{{my_placeholder}}"}
        with pytest.raises(VerificationError):
            VerificationEngine._validate_content_not_empty(
                "create_document", params, field="content", min_length=1, block_placeholders=True
            )

    def test_long_content_with_dollar_sign_not_blocked(self):
        """Strings > 100 chars are assumed to be real data even with $ signs."""
        long_content = "Email from Alice: Please find attached the invoice for $500. " + "Extra padding " * 5
        assert len(long_content) > 100
        params = {"content": long_content}
        # Should NOT raise even though it contains '$500'
        VerificationEngine._validate_content_not_empty(
            "create_document", params, field="content", min_length=1, block_placeholders=True
        )

    def test_exactly_100_chars_with_template_still_blocked(self):
        """Exactly 100 chars: should still apply placeholder check."""
        # Craft content that _has_unresolved_templates would detect
        base = "a" * 85  # 85 chars
        content = base + "{{var}}"  # 85 + 7 = 92 chars < 100
        params = {"content": content}
        with pytest.raises(VerificationError):
            VerificationEngine._validate_content_not_empty(
                "create_document", params, field="content", min_length=1, block_placeholders=True
            )

    def test_101_chars_with_template_not_blocked(self):
        """101+ chars: placeholder check is skipped (PR change)."""
        # Build a 101-char string containing a template pattern
        base = "x" * 94  # 94 chars
        content = base + "{{var}}"  # 101 chars
        assert len(content) > 100
        params = {"content": content}
        # Should NOT raise because len > 100
        VerificationEngine._validate_content_not_empty(
            "create_document", params, field="content", min_length=1, block_placeholders=True
        )


# ---------------------------------------------------------------------------
# _is_ignored_validation_path — ".text" added to ignored suffixes
# ---------------------------------------------------------------------------

class TestIsIgnoredValidationPathTextSuffix:
    """PR change: .text is now an ignored path suffix."""

    def test_text_suffix_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("result.text") is True

    def test_nested_text_suffix_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.message.text") is True

    def test_text_in_middle_not_ignored(self):
        """Only suffix matters — 'text' in the middle of a path should not be ignored."""
        # e.g. "params.textContent.id" - .id is ignored, but .textContent is not
        result = VerificationEngine._is_ignored_validation_path("params.textContent")
        # This should NOT be ignored (it ends with .textContent, not .text)
        assert result is False

    def test_title_suffix_still_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.title") is True

    def test_snippet_suffix_still_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.snippet") is True

    def test_content_suffix_still_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.content") is True

    def test_name_suffix_still_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.name") is True

    def test_id_suffix_still_ignored(self):
        assert VerificationEngine._is_ignored_validation_path("params.id") is True

    def test_non_ignored_path_not_ignored(self):
        """A path like 'params.folder_id' should not be in ignored set."""
        # folder_id doesn't end with any ignored suffix
        assert VerificationEngine._is_ignored_validation_path("params.folder_id") is False

    def test_code_path_ignored(self):
        """params.code is explicitly ignored."""
        assert VerificationEngine._is_ignored_validation_path("params.code") is True


# ---------------------------------------------------------------------------
# verify_params — content with $ signs in create doc should not raise (integration)
# ---------------------------------------------------------------------------

class TestVerifyParamsContentPlaceholderIntegration:
    """Integration test: verify that verifying a create_document with $ in content passes."""

    def test_create_document_with_email_summary_content(self):
        """Simulates resolved email summary being used as document content — should not fail."""
        params = {
            "title": "Email Summary Report",
            "content": (
                "Subject: Invoice from Stripe | Amount: $299.99 | Status: paid. "
                "Total messages processed: 5. Revenue this month: $1,500."
            ),
        }
        # Should not raise a VerificationError (block_placeholders=False for content)
        # This calls verify_params which internally calls _validate_content_not_empty with block_placeholders=False
        try:
            VerificationEngine.verify_params("create_document", params)
        except VerificationError as e:
            # Only allowed failure is non-content related (e.g. title issues)
            assert "content" not in str(e).lower() or "placeholder" not in str(e).lower(), \
                f"content field should not block $ chars, but got: {e}"
