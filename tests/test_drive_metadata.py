import pytest
from gws_assistant.execution.drive_metadata import summarize

@pytest.mark.drive
def test_summarize_count():
    payload = {
        "files": [
            {"name": "file1", "mimeType": "application/vnd.google-apps.document", "webViewLink": "http://link1"},
            {"name": "file2", "mimeType": "application/vnd.google-apps.spreadsheet", "webViewLink": "http://link2"},
        ]
    }
    result = summarize(payload)
    assert result["count"] == 2

@pytest.mark.drive
def test_summarize_table_headers():
    payload = {
        "files": [
            {"name": "file1", "mimeType": "application/vnd.google-apps.document", "webViewLink": "http://link1"},
        ]
    }
    result = summarize(payload)
    assert "Name" in result["table"]
    assert "Type" in result["table"]
    assert "Link" in result["table"]

@pytest.mark.drive
def test_summarize_empty_files():
    payload = {"files": []}
    result = summarize(payload)
    assert result["count"] == 0
    assert "Found 0 Drive files." in result["table"] # _format_drive_files behavior
    assert result["summary_rows"] == []

@pytest.mark.drive
def test_full_agent_path():
    # Full agent path: drive.list_files → summarize() → gmail body is a string not a list
    payload = {
        "files": [
            {"name": "file1", "mimeType": "application/vnd.google-apps.document", "webViewLink": "http://link1"},
        ]
    }
    result = summarize(payload)
    # The formatted table string is used in the gmail body
    assert isinstance(result["table"], str)
