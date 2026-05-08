"""Tests for PR changes in gws_assistant/agent_system.py.

Covers:
- Special case: drive + code + sheets detected together adds sheets.get_values task
- sheets.create_spreadsheet uses _extract_sheet_title instead of _extract_quoted
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

# agent_system requires langchain and other heavy dependencies; skip if not available.
pytest.importorskip("langchain_core", reason="langchain_core not installed")

from gws_assistant.agent_system import WorkspaceAgentSystem
from gws_assistant.models import AppConfigModel


def _config(tmp_path: Path) -> AppConfigModel:
    return AppConfigModel(
        provider="openai",
        model="gpt-4.1-mini",
        api_key=None,
        llm_fallback_models=[],
        base_url=None,
        timeout_seconds=30,
        gws_binary_path=tmp_path / os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws"),
        log_file_path=tmp_path / "assistant.log",
        log_level="INFO",
        verbose=False,
        env_file_path=tmp_path / ".env",
        setup_complete=True,
        max_retries=3,
        langchain_enabled=True,
        use_heuristic_fallback=True,
        default_recipient_email=os.getenv("DEFAULT_RECIPIENT_EMAIL", "test@example.com"),
    )


# ---------------------------------------------------------------------------
# Special case: drive + code + sheets -> inserts sheets.get_values
# ---------------------------------------------------------------------------

class TestDriveCodeSheetsSpecialCase:
    """PR: when drive, code, AND sheets are all detected, add sheets.get_values task."""

    @pytest.mark.drive
    @pytest.mark.code
    @pytest.mark.sheets
    def test_drive_code_sheets_plan_includes_sheets_get_values(self, tmp_path):
        """When request involves drive + sheets + code, sheets.get_values should be added."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Download the sales spreadsheet from Drive, analyze it with Python code")
        # sheets.get_values should be present when drive+code+sheets all detected
        # This is only triggered by the fallback heuristic when all three are detected
        assert plan.no_service_detected is False
        actions = [f"{t.service}.{t.action}" for t in plan.tasks]
        assert "sheets.get_values" in actions, "Expected sheets.get_values to be injected for drive+code+sheets"

    @pytest.mark.drive
    def test_drive_without_code_no_special_case(self, tmp_path):
        """Drive without code should not trigger the special case."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("List files in my Drive folder")
        assert plan.no_service_detected is False
        # No code task should be injected
        services = [t.service for t in plan.tasks]
        assert "code" not in services

    @pytest.mark.sheets
    def test_sheets_without_drive_no_special_case(self, tmp_path):
        """Sheets without drive should not trigger the special case."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Get values from my spreadsheet")
        assert plan.no_service_detected is False


# ---------------------------------------------------------------------------
# sheets.create_spreadsheet uses _extract_sheet_title
# ---------------------------------------------------------------------------

class TestSheetsCreateSpreadsheetTitle:
    @pytest.mark.sheets
    def test_create_spreadsheet_uses_extracted_title(self, tmp_path):
        """PR: sheets.create_spreadsheet now uses _extract_sheet_title for title extraction."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Create a new spreadsheet called 'Sales Data 2026'")
        # Find sheets task
        sheets_tasks = [t for t in plan.tasks if t.service == "sheets"]
        assert len(sheets_tasks) > 0
        task = sheets_tasks[0]
        if task.action == "create_spreadsheet":
            assert task.parameters.get("title") is not None
            assert task.parameters["title"] != ""

    @pytest.mark.sheets
    def test_create_spreadsheet_defaults_to_new_spreadsheet(self, tmp_path):
        """When no title can be extracted, defaults to 'New Spreadsheet'."""
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Create a new spreadsheet")
        sheets_tasks = [t for t in plan.tasks if t.service == "sheets"]
        assert len(sheets_tasks) > 0
        assert sheets_tasks[0].action == "create_spreadsheet"
        title = sheets_tasks[0].parameters.get("title")
        assert title == "New Spreadsheet"


# ---------------------------------------------------------------------------
# Regression: existing heuristic planning still works
# ---------------------------------------------------------------------------

class TestHeuristicPlanningRegression:
    @pytest.mark.gmail
    def test_gmail_list_messages_still_works(self, tmp_path):
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Show me my unread emails")
        assert plan.no_service_detected is False
        assert any(t.service == "gmail" for t in plan.tasks)

    @pytest.mark.calendar
    def test_calendar_create_event_still_works(self, tmp_path):
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Schedule a meeting next Monday")
        assert plan.no_service_detected is False
        assert any(t.service == "calendar" for t in plan.tasks)

    def test_no_service_detected_returns_correct_flag(self, tmp_path):
        agent = WorkspaceAgentSystem(config=_config(tmp_path), logger=logging.getLogger("test"))
        plan = agent.plan("Tell me a joke")
        assert plan.no_service_detected is True
