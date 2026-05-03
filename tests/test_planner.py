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
        {
            "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
            "subject": "Hello",
            "body": "Test message",
        },
    )
    assert args[:4] == ["gmail", "users", "messages", "send"]
    assert "--json" in args


def test_build_forms_batch_update_command():
    planner = CommandPlanner()
    args = planner.build_command(
        "forms",
        "batch_update",
        {
            "form_id": "form-1",
            "requests": [{"updateFormInfo": {"info": {"title": "New Title"}, "updateMask": "title"}}],
        },
    )
    assert args[:3] == ["forms", "forms", "batchUpdate"]
    assert "--params" in args
    assert "formId" in args[args.index("--params") + 1]
    assert "--json" in args
    assert "requests" in args[args.index("--json") + 1]


def test_build_gmail_send_message_rejects_attachments_during_planning():
    planner = CommandPlanner()
    with pytest.raises(ValidationError, match="materialized at execution time"):
        planner.build_command(
            "gmail",
            "send_message",
            {
                "to_email": os.getenv("DEFAULT_RECIPIENT_EMAIL") or "test@example.com",
                "subject": "Hello",
                "body": "Test message",
                "attachments": ["/etc/passwd"],
            },
        )


# -----------------------------------------------------------------------------
# Drive upload_file - folder_id parents support (PR #76 / #78)
# -----------------------------------------------------------------------------


def test_drive_upload_file_without_folder_id_omits_parents(tmp_path):
    """Without folder_id, the JSON payload must NOT include a 'parents' field."""
    import json as _json

    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"hello")

    planner = CommandPlanner()
    args = planner.build_command(
        "drive", "upload_file", {"file_path": str(file_path)}
    )
    assert args[:4] == ["drive", "files", "create", "--upload"]
    payload = _json.loads(args[args.index("--json") + 1])
    assert "parents" not in payload
    assert payload["name"] == "report.pdf"


def test_drive_upload_file_with_folder_id_sets_parents(tmp_path):
    """With folder_id, the JSON payload must set parents=[folder_id]."""
    import json as _json

    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"hello")

    planner = CommandPlanner()
    args = planner.build_command(
        "drive",
        "upload_file",
        {"file_path": str(file_path), "folder_id": "1AbCdEFg123"},
    )
    payload = _json.loads(args[args.index("--json") + 1])
    assert payload["parents"] == ["1AbCdEFg123"]


def test_drive_upload_file_rejects_unresolved_placeholder_folder_id(tmp_path):
    """Silent fallback to drive root for an unresolved placeholder is dangerous;
    raise ValidationError instead.
    """
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"hello")

    planner = CommandPlanner()
    with pytest.raises(ValidationError, match="Unresolved placeholder folder_id"):
        planner.build_command(
            "drive",
            "upload_file",
            {"file_path": str(file_path), "folder_id": "{{task-1.id}}"},
        )
