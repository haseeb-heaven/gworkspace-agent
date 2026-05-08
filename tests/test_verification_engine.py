import pytest

from gws_assistant.verification_engine import VerificationEngine, VerificationError


# CATEGORY 1: PLACEHOLDER DETECTION & GENERAL
def test_placeholder_detection():
    assert VerificationEngine._is_placeholder("{{some_value}}") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("[TBD]") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("<replace_me>") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("todo") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("noreply@example.com") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("0000") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("...") is True  # nosec B101: Test assertion
    assert VerificationEngine._is_placeholder("valid_string") is False  # nosec B101: Test assertion


def test_general_verification_fail_none():
    with pytest.raises(VerificationError, match="Result is None"):
        VerificationEngine.verify_result("some_tool", {}, None)


def test_general_verification_fail_error():
    with pytest.raises(VerificationError, match="Result contains success/ok: False"):
        VerificationEngine.verify_result("some_tool", {}, {"success": False})

    with pytest.raises(VerificationError, match="Result status is error"):
        VerificationEngine.verify_result("some_tool", {}, {"status": "error"})


def test_general_verification_fail_http_code():
    with pytest.raises(VerificationError, match="Result contains HTTP error code 404"):
        VerificationEngine.verify_result("some_tool", {}, {"code": 404})


def test_general_verification_fail_ai_returns_params_as_result():
    with pytest.raises(VerificationError, match="Result is exactly the same as params"):
        VerificationEngine.verify_result("some_tool", {"foo": "bar"}, {"foo": "bar"})


# CATEGORY 2: GMAIL
def test_gmail_send_success():
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body"}
    result = {"id": "123", "labelIds": ["SENT"]}
    VerificationEngine.verify("send_message", params, result)


def test_gmail_send_fail_placeholder_to():
    params = {"to": "<replace_me>", "subject": "Hello", "body": "This is a body"}
    with pytest.raises(VerificationError, match="Invalid 'to' email address"):
        VerificationEngine.verify_params("send_message", params)


def test_gmail_send_fail_no_label():
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body"}
    result = {"id": "123"}
    with pytest.raises(VerificationError, match="Send result missing id, labelIds, or threadId"):
        VerificationEngine.verify_result("send_message", params, result)


# CATEGORY 3: DRIVE/DOCS
def test_docs_create_success():
    params = {"title": "My Doc"}
    result = {"documentId": "docs-1234567890", "mimeType": "application/vnd.google-apps.document"}
    VerificationEngine.verify("create_document", params, result)


def test_docs_create_fail_short_title():
    params = {"title": ""}
    with pytest.raises(VerificationError, match="Document title required"):
        VerificationEngine.verify_params("create_document", params)


def test_docs_create_fail_invalid_id():
    params = {"title": "My Doc"}
    result = {"documentId": ""}  # Too short, must fail
    with pytest.raises(VerificationError, match="Result missing valid id"):
        VerificationEngine.verify_result("create_document", params, result)


# CATEGORY 4: SHEETS
def test_sheets_write_success():
    params = {"spreadsheet_id": "sheets-1234567890123", "range": "Sheet1!A1", "values": [["Hello"]]}
    result = {"updatedCells": 1}
    VerificationEngine.verify("write_sheet", params, result)


def test_sheets_write_fail_invalid_range_1():
    params = {"spreadsheet_id": "sheets-1234567890123", "range": "invalid range", "values": [["Hello"]]}
    with pytest.raises(VerificationError, match="Invalid range format"):
        VerificationEngine.verify_params("write_sheet", params)


def test_sheets_write_fail_invalid_range_2():
    params = {"spreadsheet_id": "sheets-1234567890123", "range": "Sheet1!", "values": [["Hello"]]}
    with pytest.raises(VerificationError, match="Invalid range format"):
        VerificationEngine.verify_params("write_sheet", params)


def test_sheets_write_fail_empty_values():
    params = {"spreadsheet_id": "sheets-1234567890123", "range": "Sheet1!A1", "values": [[]]}
    with pytest.raises(VerificationError, match="Values cannot be empty"):
        VerificationEngine.verify_params("write_sheet", params)


# CATEGORY 5: CALENDAR
def test_calendar_create_success():
    params = {"summary": "Meeting", "start": "2024-01-01T10:00:00Z", "end": "2024-01-01T11:00:00Z"}
    result = {"id": "cal-123", "status": "confirmed"}
    VerificationEngine.verify("create_event", params, result)


def test_calendar_create_fail_end_before_start_1():
    params = {"summary": "Meeting", "start": "2024-01-01T10:00:00Z", "end": "2024-01-01T09:00:00Z"}
    with pytest.raises(VerificationError, match="End time must be after start time"):
        VerificationEngine.verify_params("create_event", params)


def test_calendar_create_fail_end_before_start_2():
    params = {
        "summary": "Meeting",
        "start": {"dateTime": "2024-01-02T10:00:00Z"},
        "end": {"dateTime": "2024-01-01T09:00:00Z"},
    }
    with pytest.raises(VerificationError, match="End time must be after start time"):
        VerificationEngine.verify_params("create_event", params)


def test_calendar_create_fail_cancelled():
    params = {"summary": "Meeting", "start": "2024-01-01T10:00:00Z", "end": "2024-01-01T11:00:00Z"}
    result = {"id": "cal-123", "status": "cancelled"}
    with pytest.raises(VerificationError, match="Event status cancelled right after creation"):
        VerificationEngine.verify_result("create_event", params, result)


# CATEGORY 6: TASKS
def test_tasks_create_success():
    params = {"title": "Buy milk"}
    result = {"id": "task-123", "status": "needsAction"}
    VerificationEngine.verify("create_task", params, result)


def test_tasks_create_fail_placeholder_title():
    params = {"title": "[Replace me]"}
    with pytest.raises(VerificationError, match="Task title required"):
        VerificationEngine.verify_params("create_task", params)


def test_tasks_create_fail_invalid_status():
    params = {"title": "Buy milk"}
    result = {"id": "task-123", "status": "unknown_status"}
    with pytest.raises(VerificationError, match="Invalid task status unknown_status"):
        VerificationEngine.verify_result("create_task", params, result)


# CATEGORY 7: CONTACTS
def test_contacts_create_success():
    params = {"first_name": "John", "phone": "1234567890"}
    result = {"resourceName": "people/123", "names": [{"givenName": "John"}]}
    VerificationEngine.verify("create_contact", params, result)


def test_contacts_create_fail_no_name():
    params = {"phone": "1234567890"}
    with pytest.raises(VerificationError, match="first_name or display_name required"):
        VerificationEngine.verify_params("create_contact", params)


def test_contacts_create_fail_short_phone():
    params = {"first_name": "John", "phone": "123"}
    with pytest.raises(VerificationError, match="Phone number too short"):
        VerificationEngine.verify_params("create_contact", params)


# ATTACHMENT VERIFICATION
def test_attachment_verification_missing_in_result():
    params = {
        "to": "user@valid.com",
        "subject": "test",
        "body": "test",
        "attachments": [{"filename": "f.txt", "mime_type": "text/plain", "file_path": "f.txt"}],
    }
    result = {"id": "msg-1", "labelIds": ["SENT"]}  # missing parts/attachments
    with pytest.raises(VerificationError, match="Attachment declared in params but not confirmed in result"):
        VerificationEngine.verify_attachment_sent(params, result)


def test_attachment_verification_success():
    params = {
        "to": "user@valid.com",
        "subject": "test",
        "body": "test",
        "attachments": [{"filename": "f.txt", "mime_type": "text/plain", "file_path": "f.txt"}],
    }
    result = {"id": "msg-1", "labelIds": ["SENT"], "payload": {"parts": [{"filename": "f.txt"}]}}
    VerificationEngine.verify_attachment_sent(params, result)


# EMPTY DOCUMENT CHECK
def test_empty_document_create():
    params = {"title": "Doc", "content": ""}
    with pytest.raises(VerificationError, match="Operation created/wrote an empty document or sheet"):
        VerificationEngine.verify_document_not_empty("create_document", params, {})


def test_empty_sheet_write():
    params = {"spreadsheet_id": "sheets-123", "range": "A1", "values": []}
    with pytest.raises(VerificationError, match="Operation created/wrote an empty document or sheet"):
        VerificationEngine.verify_document_not_empty("write_sheet", params, {})


# ============================================================================
# NEW 5-CHECK SYSTEM TESTS
# ============================================================================

def test_5_check_system_all_pass():
    """Test that all 5 checks pass for a valid operation."""
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body"}
    result = {"id": "123", "labelIds": ["SENT"]}
    VerificationEngine.verify("gmail_send_message", params, result)


def test_5_check_system_check_1_parameter_validation():
    """Test CHECK 1: Parameter Validation fails with invalid params."""
    params = {"to": "<placeholder>", "subject": "Hello", "body": "This is a body"}
    result = {"id": "123", "labelIds": ["SENT"]}
    with pytest.raises(VerificationError, match=r"\[CHECK 1\]"):
        VerificationEngine.verify("gmail_send_message", params, result)


def test_5_check_system_check_2_permission_scope_critical():
    """Test CHECK 2: Permission & Scope Validation blocks bulk destruction."""
    params = {"query": "delete everything", "_granted_scopes": ["https://www.googleapis.com/auth/drive.readonly"]}
    result = {"success": True}
    # Matches both bulk destruction and missing scopes
    with pytest.raises(VerificationError, match=r"\[CHECK 2\].*CRITICAL"):
        VerificationEngine.verify("drive_delete_file", params, result)

def test_5_check_system_check_2_missing_scopes():
    """Test CHECK 2: Specifically test missing scopes validation."""
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body", "_granted_scopes": ["https://www.googleapis.com/auth/gmail.readonly"]}
    result = {"success": True}
    # gmail requires .modify
    with pytest.raises(VerificationError, match=r"\[CHECK 2\].*Missing required scopes"):
        VerificationEngine.verify("gmail_send_message", params, result)


def test_5_check_system_check_3_result_validation():
    """Test CHECK 3: Result Validation fails with invalid result."""
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body"}
    result = None
    with pytest.raises(VerificationError, match=r"\[CHECK 3\]"):
        VerificationEngine.verify("gmail_send_message", params, result)


def test_5_check_system_check_4_data_integrity():
    """Test CHECK 4: Data Integrity & Consistency Validation."""
    params = {"title": "Doc", "content": ""}
    result = {"id": "doc-123"}
    with pytest.raises(VerificationError, match=r"\[CHECK 4\]"):
        VerificationEngine.verify("create_document", params, result)
    # Also verify the service-prefixed variant ("docs_create_document") trips
    # CHECK 4 — naming convention must not bypass data-integrity validation.
    with pytest.raises(VerificationError, match=r"\[CHECK 4\]"):
        VerificationEngine.verify("docs_create_document", params, result)


def test_5_check_system_check_5_idempotency_safety_critical():
    """Test CHECK 5: Idempotency & Safety Validation blocks destructive ops without confirmation."""
    params = {"file_id": "file-123"}
    result = {}  # Delete operations typically return empty or minimal result
    with pytest.raises(VerificationError, match=r"\[CHECK 5\].*CRITICAL.*_safety_confirmed"):
        VerificationEngine.verify("drive_delete_file", params, result)


def test_5_check_system_destructive_with_safety_confirmed():
    """Test that destructive operations pass with _safety_confirmed=true."""
    params = {"file_id": "file-123", "_safety_confirmed": True}
    # Pass a result that passes CHECK 3 (result validation)
    result = {"success": True, "id": "file-123"}
    VerificationEngine.verify("drive_delete_file", params, result)


def test_5_check_system_bulk_operation_requires_confirmation():
    """Test that bulk operations require _bulk_confirmed=true."""
    params = {"query": "*"}
    result = {"files": []}
    with pytest.raises(VerificationError, match=r"\[CHECK 5\].*CRITICAL.*_bulk_confirmed"):
        VerificationEngine.verify("drive_batch_delete", params, result)


def test_5_check_system_bulk_with_confirmation():
    """Test that bulk operations pass with _bulk_confirmed=true."""
    params = {"query": "*", "_bulk_confirmed": True}
    result = {"files": []}
    VerificationEngine.verify("drive_batch_delete", params, result)


def test_verification_severity_enum():
    """Test VerificationSeverity enum values."""
    from gws_assistant.verification_engine import VerificationSeverity
    assert VerificationSeverity.CRITICAL.value == "CRITICAL"  # nosec B101: Test assertion
    assert VerificationSeverity.ERROR.value == "ERROR"  # nosec B101: Test assertion
    assert VerificationSeverity.WARNING.value == "WARNING"  # nosec B101: Test assertion


def test_verification_error_with_check_number():
    """Test VerificationError includes check_number and severity."""
    from gws_assistant.verification_engine import VerificationSeverity
    error = VerificationError(
        tool="test_tool",
        reason="Test reason",
        check_number=1,
        severity=VerificationSeverity.ERROR,
        field="test_field"
    )
    assert error.check_number == 1  # nosec B101: Test assertion
    assert error.severity == VerificationSeverity.ERROR  # nosec B101: Test assertion
    assert error.field == "test_field"  # nosec B101: Test assertion
    assert "[CHECK 1]" in str(error)  # nosec B101: Test assertion
    assert "[ERROR]" in str(error)  # nosec B101: Test assertion
