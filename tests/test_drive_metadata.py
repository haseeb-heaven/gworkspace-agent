import pytest
from gws_assistant.execution.drive_metadata import summarize
from gws_assistant.execution.context_updater import ContextUpdaterMixin

def test_summarize_count_and_headers():
    payload = {
        "files": [
            {"id": "1", "name": "File A", "mimeType": "application/vnd.google-apps.document", "webViewLink": "http://a"},
            {"id": "2", "name": "File B", "mimeType": "application/pdf", "webViewLink": "http://b"}
        ]
    }
    result = summarize(payload)
    assert result["count"] == 2
    assert "Name" in result["table"]
    assert "Type" in result["table"]
    assert "Link" in result["table"]
    assert "File A" in result["table"]
    assert "File B" in result["table"]
    assert len(result["summary_rows"]) == 2
    assert result["summary_rows"][0] == ["File A", "application/vnd.google-apps.document", "http://a"]

def test_summarize_empty():
    payload = {"files": []}
    result = summarize(payload)
    assert result["count"] == 0
    assert "Found 0 Drive files" in result["table"]
    assert result["summary_rows"] == []

@pytest.mark.drive
def test_full_agent_path():
    # Simulate what _update_context_from_result does
    class DummyExecutor(ContextUpdaterMixin):
        pass

    executor = DummyExecutor()
    context = {}
    payload = {
        "files": [
            {"id": "1", "name": "File A", "mimeType": "text/plain", "webViewLink": "http://a"}
        ]
    }

    executor._update_context_from_result(payload, context, None)

    # Check that drive_summary_values is a formatted string, not a list
    val = context.get("drive_summary_values")
    assert isinstance(val, str)
    assert "File A" in val
    assert "Name" in val
