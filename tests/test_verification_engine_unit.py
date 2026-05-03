"""Tests for verification_engine.py — covers helper methods, verify_params, verify_result branches."""
from __future__ import annotations

import pytest

from gws_assistant.verification_engine import VerificationEngine, VerificationError

# ---------- _is_placeholder ----------

class TestIsPlaceholder:
    def test_none_returns_false(self):
        assert VerificationEngine._is_placeholder(None) is False

    def test_empty_string_is_placeholder(self):
        assert VerificationEngine._is_placeholder("") is True

    def test_exact_placeholders(self):
        for p in ("none", "null", "todo", "fixme", "placeholder", "default", "tbd"):
            assert VerificationEngine._is_placeholder(p) is True, f"{p} should be placeholder"

    def test_numeric_placeholders(self):
        for p in ("0000", "1234", "9999"):
            assert VerificationEngine._is_placeholder(p) is True

    def test_bracketed_placeholders(self):
        assert VerificationEngine._is_placeholder("<value>") is True
        assert VerificationEngine._is_placeholder("[value]") is True
        assert VerificationEngine._is_placeholder("{{value}}") is True

    def test_special_chars_only(self):
        assert VerificationEngine._is_placeholder("---") is True

    def test_real_values_not_placeholder(self):
        assert VerificationEngine._is_placeholder("Hello World") is False
        assert VerificationEngine._is_placeholder("abc123") is False
        assert VerificationEngine._is_placeholder("user@real.com") is False


# ---------- _is_valid_email ----------

class TestIsValidEmail:
    def test_valid_email(self):
        assert VerificationEngine._is_valid_email("test@example.org") is True

    def test_placeholder_email(self):
        assert VerificationEngine._is_valid_email("noreply@example.com") is False

    def test_test_domain_email(self):
        assert VerificationEngine._is_valid_email("user@test.com") is False

    def test_invalid_format(self):
        assert VerificationEngine._is_valid_email("not-an-email") is False


# ---------- _is_valid_iso8601 ----------

class TestIsValidIso8601:
    def test_date_string(self):
        assert VerificationEngine._is_valid_iso8601("2024-12-25") is True

    def test_datetime_string(self):
        assert VerificationEngine._is_valid_iso8601("2024-12-25T10:00:00") is True

    def test_dict_with_dateTime(self):
        assert VerificationEngine._is_valid_iso8601({"dateTime": "2024-12-25T10:00:00"}) is True

    def test_dict_with_date(self):
        assert VerificationEngine._is_valid_iso8601({"date": "2024-12-25"}) is True

    def test_invalid_date(self):
        assert VerificationEngine._is_valid_iso8601("not-a-date") is False

    def test_empty(self):
        assert VerificationEngine._is_valid_iso8601("") is False
        assert VerificationEngine._is_valid_iso8601(None) is False


# ---------- _is_valid_drive_id ----------

class TestIsValidDriveId:
    def test_valid_ids(self):
        assert VerificationEngine._is_valid_drive_id("1AbCdEFg123") is True
        assert VerificationEngine._is_valid_drive_id("sheet-abc") is True
        assert VerificationEngine._is_valid_drive_id("$last_id") is True
        assert VerificationEngine._is_valid_drive_id("{{spreadsheet_id}}") is True

    def test_invalid_id(self):
        assert VerificationEngine._is_valid_drive_id("") is False


# ---------- _is_valid_url ----------

class TestIsValidUrl:
    def test_valid_url(self):
        assert VerificationEngine._is_valid_url("https://example.com") is True

    def test_invalid_url(self):
        assert VerificationEngine._is_valid_url("ftp://nope") is False


# ---------- _end_is_after_start ----------

class TestEndIsAfterStart:
    def test_end_after_start(self):
        assert VerificationEngine._end_is_after_start("2024-01-01", "2024-01-02") is True

    def test_end_before_start(self):
        assert VerificationEngine._end_is_after_start("2024-01-02", "2024-01-01") is False

    def test_missing_values(self):
        assert VerificationEngine._end_is_after_start(None, None) is True

    def test_dict_values(self):
        assert VerificationEngine._end_is_after_start(
            {"dateTime": "2024-01-01T10:00:00"},
            {"dateTime": "2024-01-01T11:00:00"},
        ) is True


# ---------- verify_params ----------

class TestVerifyParams:
    def test_gmail_send_valid(self):
        VerificationEngine.verify_params("gmail_send_message", {
            "to": "real@example.org",
            "subject": "Test Subject",
            "body": "Hello, this is a valid body.",
        })

    def test_gmail_send_invalid_email(self):
        with pytest.raises(VerificationError, match="Invalid 'to'"):
            VerificationEngine.verify_params("gmail_send_message", {
                "to": "placeholder",
                "subject": "Test",
                "body": "Hello body text",
            })

    def test_gmail_send_missing_body(self):
        with pytest.raises(VerificationError, match="empty or whitespace"):
            VerificationEngine.verify_params("gmail_send_message", {
                "to": "real@example.org",
                "subject": "Test Subject",
                "body": "",
            })

    def test_drive_create_valid(self):
        VerificationEngine.verify_params("drive_create_file", {
            "title": "My Document",
        })

    def test_drive_create_missing_title(self):
        with pytest.raises(VerificationError, match="folder_name"):
            VerificationEngine.verify_params("drive_create_file", {})

    def test_sheets_valid_range(self):
        VerificationEngine.verify_params("sheets_append_values", {
            "spreadsheet_id": "1AbCdEFg123",
            "range": "Sheet1!A1:B10",
            "values": [["a", "b"]],
        })

    def test_sheets_invalid_range(self):
        with pytest.raises(VerificationError, match="range"):
            VerificationEngine.verify_params("sheets_append_values", {
                "spreadsheet_id": "1AbCdEFg123",
                "range": "!!!invalid",
                "values": [["a", "b"]],
            })

    def test_calendar_create_valid(self):
        VerificationEngine.verify_params("calendar_create_event", {
            "summary": "Team Meeting",
            "start_date": "2024-12-25",
        })

    def test_calendar_create_missing_summary(self):
        with pytest.raises(VerificationError, match="summary"):
            VerificationEngine.verify_params("calendar_create_event", {
                "summary": "",
                "start_date": "2024-12-25",
            })


# ---------- verify_result ----------

class TestVerifyResult:
    def test_gmail_send_result_valid(self):
        VerificationEngine.verify_result("gmail_send_message", {}, {
            "id": "msg123",
            "labelIds": ["SENT"],
            "threadId": "thread123",
        })

    def test_drive_create_result_missing_id(self):
        with pytest.raises(VerificationError, match="missing valid id"):
            VerificationEngine.verify_result("drive_create_file", {}, {"name": "test"})

    def test_sheets_create_result_valid(self):
        VerificationEngine.verify_result("sheets_create_spreadsheet", {}, {
            "spreadsheetId": "1AbCdEFg123",
        })

    def test_calendar_cancelled_event(self):
        with pytest.raises(VerificationError, match="cancelled"):
            VerificationEngine.verify_result("calendar_create_event", {}, {
                "id": "event123",
                "status": "cancelled",
            })

    def test_tasks_invalid_status(self):
        with pytest.raises(VerificationError, match="Invalid task status"):
            VerificationEngine.verify_result("tasks_create_task", {}, {
                "id": "task123",
                "status": "invalid_status",
            })


# ---------- verify_attachment_sent ----------

class TestVerifyAttachmentSent:
    def test_no_attachments_no_error(self):
        VerificationEngine.verify_attachment_sent({}, {})

    def test_attachment_with_parts_passes(self):
        VerificationEngine.verify_attachment_sent(
            {"attachments": ["file.pdf"]},
            {"payload": {"parts": [{"filename": "file.pdf"}]}},
        )

    def test_attachment_without_parts_warns(self):
        with pytest.raises(VerificationError, match="not confirmed"):
            VerificationEngine.verify_attachment_sent(
                {"attachments": ["file.pdf"]},
                {"payload": {}},
            )


# ---------- verify_document_not_empty ----------

class TestVerifyDocumentNotEmpty:
    def test_non_empty_passes(self):
        VerificationEngine.verify_document_not_empty(
            "create_document", {"content": "Hello"}, {}
        )

    def test_empty_content_raises(self):
        with pytest.raises(VerificationError, match="empty document"):
            VerificationEngine.verify_document_not_empty(
                "create_document", {"content": ""}, {}
            )

    def test_empty_values_raises(self):
        with pytest.raises(VerificationError, match="empty document"):
            VerificationEngine.verify_document_not_empty(
                "append_values", {"values": []}, {}
            )


# ---------- verify (integration of all sub-checks) ----------

class TestVerifyIntegration:
    def test_full_verify_gmail_send(self):
        VerificationEngine.verify("gmail_send_message", {
            "to": "real@example.org",
            "subject": "Test Subject",
            "body": "Hello, this is a valid body.",
        }, {
            "id": "msg123",
            "labelIds": ["SENT"],
            "threadId": "thread123",
        })

    def test_full_verify_non_dict_params(self):
        # verify handles non-dict params gracefully
        VerificationEngine.verify("unknown_tool", "not_a_dict", {})
