"""Tests for cli_app module — covers helper functions and typer callback branches."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gws_assistant.cli_app import _save_output, _ask_non_empty


class TestSaveOutput:
    """Covers the _save_output helper."""

    def test_save_output_creates_file(self, tmp_path: Path):
        target = tmp_path / "subdir" / "output.txt"
        _save_output(target, "hello world")
        assert target.exists()
        assert "hello world" in target.read_text(encoding="utf-8")

    def test_save_output_appends(self, tmp_path: Path):
        target = tmp_path / "output.txt"
        _save_output(target, "first")
        _save_output(target, "second")
        content = target.read_text(encoding="utf-8")
        assert "first" in content
        assert "second" in content


class TestAskNonEmpty:
    """Covers _ask_non_empty input loop."""

    @patch("gws_assistant.cli_app.Prompt.ask", return_value="hello")
    def test_returns_non_empty(self, mock_ask):
        assert _ask_non_empty("prompt") == "hello"

    @patch("gws_assistant.cli_app.Prompt.ask", side_effect=["", "  ", "valid"])
    def test_loops_on_empty(self, mock_ask):
        assert _ask_non_empty("prompt") == "valid"
        assert mock_ask.call_count == 3

    @patch("gws_assistant.cli_app.Prompt.ask", return_value="override")
    def test_with_default(self, mock_ask):
        assert _ask_non_empty("prompt", default="default_val") == "override"


class TestAssistantCLI:
    @patch("gws_assistant.cli_app.AppConfig.from_env")
    @patch("gws_assistant.cli_app.setup_logging")
    def test_cli_initialization(self, mock_logging, mock_config):
        from gws_assistant.cli_app import AssistantCLI
        config = MagicMock()
        config.gws_binary_path = Path("gws")
        mock_config.return_value = config
        
        with patch("gws_assistant.cli_app.IntentParser"):
            with patch("gws_assistant.cli_app.CommandPlanner"):
                with patch("gws_assistant.cli_app.GWSRunner"):
                    cli = AssistantCLI()
                    assert cli is not None

    @patch("gws_assistant.cli_app.AppConfig.from_env")
    def test_cli_should_stop(self, mock_config):
        from gws_assistant.cli_app import AssistantCLI
        cli = AssistantCLI()
        assert cli._should_stop("exit") is True
        assert cli._should_stop("quit") is True
        assert cli._should_stop("bye") is True
        assert cli._should_stop("list files") is False
