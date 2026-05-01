from unittest.mock import MagicMock, patch

from gws_assistant.tools.e2b_sandbox import execute_with_e2b


def test_execute_with_e2b_missing_lib():
    with patch("gws_assistant.tools.e2b_sandbox.Sandbox", None):
        result = execute_with_e2b("print(1)", "key")
        assert result["success"] is False
        assert "not installed" in result["error"]

@patch("gws_assistant.tools.e2b_sandbox.Sandbox")
def test_execute_with_e2b_success(mock_sandbox_class):
    mock_sbx = mock_sandbox_class.return_value.__enter__.return_value
    mock_execution = MagicMock()
    mock_execution.logs.stdout = ["hello"]
    mock_execution.logs.stderr = []
    mock_execution.results = [MagicMock(json='{"x": 1}', value={"x": 1})]
    mock_execution.error = None
    mock_sbx.run_code.return_value = mock_execution

    result = execute_with_e2b("print('hello')", "key")
    assert result["success"] is True
    assert result["output"]["stdout"] == "hello"
    assert result["output"]["parsed_value"] == {"x": 1}

@patch("gws_assistant.tools.e2b_sandbox.Sandbox")
def test_execute_with_e2b_error(mock_sandbox_class):
    mock_sbx = mock_sandbox_class.return_value.__enter__.return_value
    mock_execution = MagicMock()
    mock_execution.logs.stdout = []
    mock_execution.logs.stderr = ["error"]
    mock_execution.results = []
    mock_execution.error = MagicMock(name="RuntimeError", value="failure")
    mock_sbx.run_code.return_value = mock_execution

    result = execute_with_e2b("1/0", "key")
    assert result["success"] is False
    assert "RuntimeError" in result["error"]

def test_execute_with_e2b_exception():
    with patch("gws_assistant.tools.e2b_sandbox.Sandbox") as mock_sandbox_class:
        mock_sandbox_class.side_effect = Exception("creation failed")
        result = execute_with_e2b("print(1)", "key")
        assert result["success"] is False
        assert "creation failed" in result["error"]
