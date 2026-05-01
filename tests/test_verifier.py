"""Comprehensive tests for execution/verifier.py — covers TripleVerifier, validate_artifact_content, VerifierMixin."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gws_assistant.execution.verifier import (
    TripleVerifier,
    VerifierMixin,
    validate_artifact_content,
)

# ---------- validate_artifact_content ----------

class TestValidateArtifactContent:
    def test_none_raises(self):
        with pytest.raises(ValueError, match="contains None"):
            validate_artifact_content(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("   ")

    def test_null_string_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("null")

    def test_nan_string_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("NaN")

    def test_undefined_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("undefined")

    def test_unresolved_placeholder_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("___UNRESOLVED_PLACEHOLDER___")

    def test_mustache_placeholder_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("{{some_value}}")

    def test_dollar_placeholder_raises(self):
        with pytest.raises(ValueError, match="invalid value"):
            validate_artifact_content("$spreadsheet_id")

    def test_valid_string_passes(self):
        validate_artifact_content("Hello World")

    def test_valid_number_passes(self):
        validate_artifact_content(42)

    def test_dict_with_invalid_value_raises(self):
        with pytest.raises(ValueError, match="artifact.key"):
            validate_artifact_content({"key": None})

    def test_list_with_invalid_value_raises(self):
        with pytest.raises(ValueError, match="artifact\\[0\\]"):
            validate_artifact_content([None])

    def test_nested_dict_passes(self):
        validate_artifact_content({"a": {"b": "valid"}, "c": [1, 2, "ok"]})

    def test_set_with_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_artifact_content({None})


# ---------- TripleVerifier ----------

class TestTripleVerifier:
    def _make_verifier(self, runner=None, planner=None, attempts=3):
        return TripleVerifier(
            runner=runner or MagicMock(),
            planner=planner,
            attempts=attempts,
            sleep_seconds=0.0,
        )

    def test_unknown_service_returns_false(self):
        v = self._make_verifier()
        assert v.verify_resource("unknown_service", "id123") is False

    def test_empty_resource_id_returns_false(self):
        v = self._make_verifier()
        assert v.verify_resource("sheets", "") is False

    def test_whitespace_resource_id_returns_false(self):
        v = self._make_verifier()
        assert v.verify_resource("sheets", "   ") is False

    def test_successful_verification(self):
        runner = MagicMock()
        runner.run.return_value = MagicMock(
            success=True, stdout='{"spreadsheetId": "abc123"}', output=None
        )
        v = self._make_verifier(runner=runner, attempts=2)
        assert v.verify_resource("sheets", "abc123") is True
        assert runner.run.call_count == 2

    def test_failed_run_returns_false(self):
        runner = MagicMock()
        runner.run.return_value = MagicMock(success=False, error="Not found", stderr="404")
        v = self._make_verifier(runner=runner, attempts=1)
        assert v.verify_resource("sheets", "abc123") is False

    def test_field_validation_fails(self):
        runner = MagicMock()
        runner.run.return_value = MagicMock(
            success=True, stdout='{"title": "wrong"}', output=None
        )
        v = self._make_verifier(runner=runner, attempts=1)
        assert v.verify_resource("sheets", "abc123", {"title": "expected"}) is False

    def test_field_validation_passes(self):
        runner = MagicMock()
        runner.run.return_value = MagicMock(
            success=True, stdout='{"title": "correct"}', output=None
        )
        v = self._make_verifier(runner=runner, attempts=1)
        assert v.verify_resource("sheets", "abc123", {"title": "correct"}) is True

    def test_uses_planner_build_command(self):
        runner = MagicMock()
        runner.run.return_value = MagicMock(success=True, stdout='{}', output=None)
        planner = MagicMock()
        planner.build_command.return_value = ["sheets", "spreadsheets", "get"]
        v = self._make_verifier(runner=runner, planner=planner, attempts=1)
        v.verify_resource("sheets", "abc123")
        planner.build_command.assert_called_once()

    def test_build_command_without_planner_all_services(self):
        v = self._make_verifier()
        for service in ("sheets", "docs", "drive", "gmail", "calendar", "keep", "tasks"):
            cmd = v._build_command(service, "test_id")
            assert isinstance(cmd, list)
            assert len(cmd) > 0

    def test_build_command_unknown_service_raises(self):
        v = self._make_verifier()
        with pytest.raises(ValueError, match="Unsupported service"):
            v._build_command("unknown", "id")

    def test_resource_map_contains_new_services(self):
        """Test that _RESOURCE_MAP contains entries for the four new verifier services."""
        from gws_assistant.execution.verifier import TripleVerifier
        assert "slides" in TripleVerifier._RESOURCE_MAP
        assert TripleVerifier._RESOURCE_MAP["slides"] == ("get_presentation", "presentation_id")
        assert "forms" in TripleVerifier._RESOURCE_MAP
        assert TripleVerifier._RESOURCE_MAP["forms"] == ("get_form", "form_id")
        assert "chat" in TripleVerifier._RESOURCE_MAP
        assert TripleVerifier._RESOURCE_MAP["chat"] == ("get_message", "name")
        assert "contacts" in TripleVerifier._RESOURCE_MAP
        assert TripleVerifier._RESOURCE_MAP["contacts"] == ("get_person", "resourceName")

    def test_build_command_slides(self):
        """Test _build_command for slides service."""
        v = self._make_verifier()
        cmd = v._build_command("slides", "test_presentation_id")
        assert isinstance(cmd, list)
        assert "slides" in cmd
        assert "presentations" in cmd
        assert "get" in cmd
        assert any("test_presentation_id" in str(part) for part in cmd)

    def test_build_command_forms(self):
        """Test _build_command for forms service."""
        v = self._make_verifier()
        cmd = v._build_command("forms", "test_form_id")
        assert isinstance(cmd, list)
        assert "forms" in cmd
        assert "get" in cmd
        assert any("test_form_id" in str(part) for part in cmd)

    def test_build_command_chat(self):
        """Test _build_command for chat service."""
        v = self._make_verifier()
        cmd = v._build_command("chat", "spaces/abc123/messages/def456")
        assert isinstance(cmd, list)
        assert "chat" in cmd
        assert "spaces" in cmd
        assert "messages" in cmd
        assert "get" in cmd
        assert any("spaces/abc123/messages/def456" in str(part) for part in cmd)

    def test_build_command_contacts(self):
        """Test _build_command for contacts service."""
        v = self._make_verifier()
        cmd = v._build_command("contacts", "people/test_resource_name")
        assert isinstance(cmd, list)
        assert "people" in cmd
        assert "get" in cmd
        assert any("people/test_resource_name" in str(part) for part in cmd)

    def test_payload_uses_output_attr(self):
        result = MagicMock(output={"key": "val"}, stdout='{}')
        payload = TripleVerifier._payload(result)
        assert payload == {"key": "val"}

    def test_payload_falls_back_to_stdout(self):
        result = MagicMock(output=None, stdout='{"key": "val"}')
        payload = TripleVerifier._payload(result)
        assert payload == {"key": "val"}

    def test_validate_expected_fields_no_fields(self):
        TripleVerifier._validate_expected_fields({"a": 1}, {})

    def test_validate_expected_fields_mismatch(self):
        with pytest.raises(ValueError, match="expected title"):
            TripleVerifier._validate_expected_fields({"title": "wrong"}, {"title": "right"})

    def test_validate_expected_fields_non_dict(self):
        with pytest.raises(ValueError, match="not an object"):
            TripleVerifier._validate_expected_fields("string", {"key": "val"})


# ---------- VerifierMixin ----------

class TestVerifierMixin:
    def test_verify_resource_delegates(self):
        class MyClass(VerifierMixin):
            pass
        obj = MyClass()
        obj.runner = MagicMock()
        obj.runner.run.return_value = MagicMock(success=True, stdout='{}', output=None)
        obj.planner = None
        obj.logger = MagicMock()
        assert obj.verify_resource("sheets", "abc123") is True

    def test_verify_artifact_content_delegates(self):
        class MyClass(VerifierMixin):
            pass
        obj = MyClass()
        obj.runner = MagicMock()
        obj.planner = None
        obj.logger = MagicMock()
        with pytest.raises(ValueError):
            obj._verify_artifact_content(None)
