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


# ---------------------------------------------------------------------------
# drive.upload_file — folder_id support
# ---------------------------------------------------------------------------


import json
import tempfile


class TestUploadFileWithFolderId:
    """CommandPlanner.build_command('drive', 'upload_file', ...) folder_id support."""

    planner = CommandPlanner()

    def _make_temp_file(self, suffix=".txt") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        return path

    def test_upload_without_folder_id_has_no_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" not in body

    def test_upload_with_folder_id_adds_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "folder-abc123"}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" in body
        assert body["parents"] == ["folder-abc123"]

    def test_upload_with_empty_folder_id_has_no_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": ""}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" not in body

    def test_upload_with_whitespace_folder_id_has_no_parents(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "   "}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "parents" not in body

    def test_upload_rejects_unresolved_placeholder_folder_id(self):
        """An unresolved task-chain placeholder (e.g. ``{{task-1.id}}``) must NOT
        leak through to the Drive API — Drive returns an opaque 400 in that
        case. Surface a ValidationError so the orchestrator can re-plan.
        """
        tmp = self._make_temp_file()
        with pytest.raises(ValidationError, match="Unresolved placeholder folder_id"):
            self.planner.build_command(
                "drive",
                "upload_file",
                {"file_path": tmp, "folder_id": "{{task-1.id}}"},
            )

    def test_upload_payload_still_contains_name(self):
        tmp = self._make_temp_file(suffix=".csv")
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "folder-xyz"}
        )
        body = json.loads(args[args.index("--json") + 1])
        assert "name" in body

    def test_upload_command_starts_with_drive_files_create(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "some-folder"}
        )
        assert args[:3] == ["drive", "files", "create"]

    def test_upload_command_includes_upload_flag(self):
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive", "upload_file", {"file_path": tmp, "folder_id": "some-folder"}
        )
        assert "--upload" in args
        upload_idx = args.index("--upload")
        assert args[upload_idx + 1] == tmp

    def test_upload_rejects_missing_file(self):
        with pytest.raises(ValidationError, match="File not found"):
            self.planner.build_command(
                "drive",
                "upload_file",
                {"file_path": "/nonexistent/path/file.txt", "folder_id": "folder-1"},
            )

    def test_upload_json_is_ascii_safe(self):
        # ensure_ascii=True means non-ASCII chars are escaped
        tmp = self._make_temp_file()
        args = self.planner.build_command(
            "drive",
            "upload_file",
            {"file_path": tmp, "folder_id": "folder-\u00e9"},
        )
        json_str = args[args.index("--json") + 1]
        # The JSON string should be representable as pure ASCII bytes
        json_str.encode("ascii")  # raises if non-ASCII present
