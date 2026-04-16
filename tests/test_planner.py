from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()
import os

import pytest

from gws_assistant.exceptions import ValidationError
from gws_assistant.planner import CommandPlanner


def test_list_services_contains_expected_services():
    planner = CommandPlanner()
    services = planner.list_services()
    assert "drive" in services
    assert "sheets" in services
    assert "gmail" in services
    assert "calendar" in services


def test_build_drive_list_command_uses_default_page_size():
    planner = CommandPlanner()
    args = planner.build_command("drive", "list_files", {})
    assert args[:3] == ["drive", "files", "list"]
    assert "--params" in args


def test_build_calendar_create_event_requires_parameters():
    planner = CommandPlanner()
    with pytest.raises(ValidationError):
        planner.build_command("calendar", "create_event", {"summary": "Test"})


def test_build_command_rejects_unknown_service():
    planner = CommandPlanner()
    with pytest.raises(ValidationError):
        planner.build_command("unknown", "list", {})


def test_build_sheets_get_values_command():
    planner = CommandPlanner()
    args = planner.build_command("sheets", "get_values", {"spreadsheet_id": "sheet-1", "range": "Sheet1!A1:B2"})
    assert args == ["sheets", "+read", "--spreadsheet", "sheet-1", "--range", "Sheet1!A1:B2"]


def test_build_gmail_send_message_command():
    planner = CommandPlanner()
    args = planner.build_command(
        "gmail",
        "send_message",
        {"to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL", "user@example.com"), "subject": "Hello", "body": "Test message"},
    )
    assert args[:4] == ["gmail", "users", "messages", "send"]
    assert "--json" in args
