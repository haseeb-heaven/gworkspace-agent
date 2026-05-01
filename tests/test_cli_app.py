"""Tests for cli_app module — covers helper functions and typer callback branches."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gws_assistant.cli_app import _ask_non_empty, _save_output


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
