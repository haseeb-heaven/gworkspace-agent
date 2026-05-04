"""Tests for conversation.py — covers ConversationEngine methods."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from gws_assistant.conversation import ConversationEngine
from gws_assistant.exceptions import ValidationError
from gws_assistant.models import ExecutionResult, Intent, ParameterSpec


@pytest.fixture
def mock_planner():
    planner = MagicMock()
    planner.list_services.return_value = ["drive", "gmail"]
    planner.list_actions.return_value = [MagicMock(key="list_files"), MagicMock(key="create_file")]
    planner.required_parameters.return_value = (ParameterSpec(name="q", prompt="Enter search query", example="report"),)
    planner.ensure_service.side_effect = lambda s: s
    planner.ensure_action.side_effect = lambda s, a: a
    return planner


@pytest.fixture
def mock_parser():
    return MagicMock()


@pytest.fixture
def logger():
    return logging.getLogger("test_conversation")


class TestConversationEngine:
    def test_parse_user_request_without_parser_raises(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        with pytest.raises(RuntimeError, match="not initialised with an IntentParser"):
            engine.parse_user_request("hello")

    def test_parse_user_request_delegates_to_parser(self, mock_planner, mock_parser, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger, parser=mock_parser)
        mock_parser.parse.return_value = Intent(raw_text="send email", service="gmail", action="send")
        result = engine.parse_user_request("send email")
        assert result.service == "gmail"
        mock_parser.parse.assert_called_once_with("send email")

    def test_needs_service_clarification(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        # Empty service
        assert engine.needs_service_clarification(Intent(raw_text="help", service=None)) is True
        # Unknown service
        assert engine.needs_service_clarification(Intent(raw_text="help", service="unknown")) is True
        # Known service
        assert engine.needs_service_clarification(Intent(raw_text="help", service="drive")) is False

    def test_service_clarification_message(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        msg = engine.service_clarification_message()
        assert "drive" in msg
        assert "gmail" in msg

    def test_action_choices(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        choices = engine.action_choices("drive")
        assert choices == ["list_files", "create_file"]

    def test_parameter_specs(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        specs = engine.parameter_specs("drive", "list_files")
        assert len(specs) == 1
        assert specs[0].name == "q"

    def test_merge_parameters(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        intent = Intent(raw_text="search", service="drive", parameters={"q": "name = 'test'"})
        # No interactive params
        merged = engine.merge_parameters(intent)
        assert merged == {"q": "name = 'test'"}
        # With interactive params
        merged = engine.merge_parameters(intent, {"folder_id": "123", "q": None})
        assert merged == {"q": "name = 'test'", "folder_id": "123"}
        # Override with interactive params
        merged = engine.merge_parameters(intent, {"q": "new query"})
        assert merged == {"q": "new query"}

    def test_build_command(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        mock_planner.build_command.return_value = ["drive", "files", "list"]
        cmd = engine.build_command("drive", "list_files", {"q": "test"})
        assert cmd == ["drive", "files", "list"]
        mock_planner.build_command.assert_called_once_with("drive", "list_files", {"q": "test"})

    def test_validate_selection_missing_service(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        with pytest.raises(ValidationError, match="Service is required"):
            engine.validate_selection(None, "list")

    def test_validate_selection_valid(self, mock_planner, logger):
        engine = ConversationEngine(planner=mock_planner, logger=logger)
        s, a = engine.validate_selection("drive", "list_files")
        assert s == "drive"
        assert a == "list_files"

    def test_format_result(self, mock_planner, logger):
        result = ExecutionResult(success=True, command=["ls"], stdout="output")
        formatted = ConversationEngine.format_result(result)
        assert "output" in formatted
