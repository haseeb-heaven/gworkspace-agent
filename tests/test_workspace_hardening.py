import pytest

from gws_assistant.execution.context_updater import ContextUpdaterMixin
from gws_assistant.tools.code_execution import execute_generated_code
from gws_assistant.verification_engine import VerificationEngine, VerificationError


class MockTask:
    def __init__(self, service, action, parameters=None):
        self.service = service
        self.action = action
        self.parameters = parameters or {}

def test_verification_engine_allows_unresolved_in_code():
    """Verify that VerificationEngine allows unresolved placeholders in code parameters."""
    params = {
        "code": "print('Hello {{task-1}}')\nresult = '___UNRESOLVED_PLACEHOLDER___'"
    }
    # This should NOT raise VerificationError now
    VerificationEngine.verify_pre_execution("code_execute", params)

def test_verification_engine_still_blocks_unresolved_in_gmail():
    """Verify that VerificationEngine still blocks unresolved placeholders in critical fields."""
    params = {
        "to_email": "test@example.com",
        "subject": "Hello {{task-1}}",
        "body": "Body with ___UNRESOLVED_PLACEHOLDER___"
    }
    with pytest.raises(VerificationError, match="contains unresolved template variable"):
        VerificationEngine.verify_pre_execution("gmail_send_message", params)

def test_context_updater_promotes_drive_metadata():
    """Verify that drive.get_file metadata is promoted to spreadsheet titles for auto-fix."""
    updater = ContextUpdaterMixin()
    context = {}
    data = {
        "id": "sheet-id-123",
        "name": "My Financial Data",
        "mimeType": "application/vnd.google-apps.spreadsheet"
    }
    task = MockTask("drive", "get_file")

    updater._update_context_from_result(data, context, task)

    assert context.get("last_spreadsheet_id") == "sheet-id-123"
    assert context.get("last_spreadsheet_title") == "My Financial Data"

def test_sandbox_allows_statistics_import():
    """Verify that the code sandbox allows the statistics module."""
    code = """
import statistics
data = [10, 20, 30, 40]
result = statistics.mean(data)
"""
    res = execute_generated_code(code)
    assert res["success"] is True
    assert res["output"]["parsed_value"] == 25.0

def test_context_updater_promotes_doc_metadata():
    """Verify that drive.get_file metadata is promoted to document titles."""
    updater = ContextUpdaterMixin()
    context = {}
    data = {
        "id": "doc-id-456",
        "name": "My Proposal",
        "mimeType": "application/vnd.google-apps.document"
    }
    task = MockTask("drive", "get_file")

    updater._update_context_from_result(data, context, task)

    assert context.get("last_document_id") == "doc-id-456"
    assert context.get("last_document_title") == "My Proposal"

def test_sandbox_auto_fixes_semicolons():
    """Verify that the sandbox fixes one-liners with semicolons (common LLM error)."""
    # Note: execute_generated_code has a heuristic to replace "; " with "\n" if validation fails
    code = "import math; x = 10; result = math.sqrt(x * 10)"
    res = execute_generated_code(code)
    assert res["success"] is True
    assert res["output"]["parsed_value"] == 10.0

def test_sandbox_strips_open_calls():
    """Verify that open() calls are neutralized in the sandbox."""
    code = """
with open('secrets.txt', 'r') as f:
    result = f.read()
"""
    class MockFile:
        def read(self): return "Simulated Data"
    extra_globals = {"injected_vars": [MockFile()]}
    res = execute_generated_code(code, extra_globals=extra_globals)
    assert res["success"] is True, f"Error: {res.get('error')}"
    assert res["output"]["parsed_value"] == "Simulated Data"

def test_sandbox_math_and_re_availability():
    """Verify math and re are available without explicit imports."""
    code = """
result = math.sqrt(144) + len(re.findall(r'a', 'banana'))
"""
    res = execute_generated_code(code)
    assert res["success"] is True
    assert res["output"]["parsed_value"] == 15.0  # 12 + 3

if __name__ == "__main__":
    pytest.main([__file__])
