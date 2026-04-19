import pytest

from gws_assistant.verification_engine import VerificationEngine, VerificationError


# CATEGORY 1: PLACEHOLDER DETECTION & GENERAL
def test_placeholder_detection():
    assert VerificationEngine._is_placeholder("{{some_value}}") is True
    assert VerificationEngine._is_placeholder("[TBD]") is True
    assert VerificationEngine._is_placeholder("<replace_me>") is True
    assert VerificationEngine._is_placeholder("todo") is True
    assert VerificationEngine._is_placeholder("test@example.com") is True
    assert VerificationEngine._is_placeholder("0000") is True
    assert VerificationEngine._is_placeholder("...") is True
    assert VerificationEngine._is_placeholder("valid_string") is False

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
    params = {"to": "test@example.com", "subject": "Hello", "body": "This is a body"}
    with pytest.raises(VerificationError, match="Invalid 'to' email address"):
        VerificationEngine.verify_params("send_message", params)

def test_gmail_send_fail_no_label():
    params = {"to": "valid@example.org", "subject": "Hello", "body": "This is a body"}
    result = {"id": "123"}
    with pytest.raises(VerificationError, match="Send result missing labelIds or threadId"):
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
    result = {"documentId": "123"} # Too short, must fail
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
    params = {"summary": "Meeting", "start": {"dateTime": "2024-01-02T10:00:00Z"}, "end": {"dateTime": "2024-01-01T09:00:00Z"}}
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
    params = {"to": "user@valid.com", "subject": "test", "body": "test", "attachments": [{"filename": "f.txt", "mime_type": "text/plain", "file_path": "f.txt"}]}
    result = {"id": "msg-1", "labelIds": ["SENT"]} # missing parts/attachments
    with pytest.raises(VerificationError, match="Attachment declared in params but not confirmed in result"):
        VerificationEngine.verify_attachment_sent(params, result)

def test_attachment_verification_success():
    params = {"to": "user@valid.com", "subject": "test", "body": "test", "attachments": [{"filename": "f.txt", "mime_type": "text/plain", "file_path": "f.txt"}]}
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
