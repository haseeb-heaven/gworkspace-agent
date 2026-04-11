from gws_assistant.tools.code_execution import code_execution_tool


def test_code_execution_tool_basic_math():
    result = code_execution_tool.invoke({"code": "print(2 + 2)"})
    assert result["success"] is True
    assert result["stdout"].strip() == "4"


def test_code_execution_tool_restricted_import():
    result = code_execution_tool.invoke({"code": "import os\nprint(os.name)"})
    assert result["success"] is False
    assert "SecurityError" in (result["error"] or "") or "ImportError" in (result["error"] or "")


def test_code_execution_tool_timeout():
    result = code_execution_tool.invoke({"code": "while True: pass"})
    assert result["success"] is False
    assert "TimeoutError" in (result["error"] or "")


def test_code_execution_tool_returns_structured_contract():
    result = code_execution_tool.invoke({"code": "result = {'a': 1}\nprint('done')"})
    assert set(["success", "output", "error"]).issubset(result.keys())
    assert result["output"]["parsed_value"] == {"a": 1}
