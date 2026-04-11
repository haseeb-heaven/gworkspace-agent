import pytest
from gws_assistant.tools.code_execution import code_execution_tool

def test_code_execution_tool_basic_math():
    code = "print(2 + 2)"
    result = code_execution_tool.invoke({"code": code})
    if not result["success"]:
         print(f"DEBUG Result: {result}")
    assert result["success"] is True
    assert result["stdout"].strip() == "4"

def test_code_execution_tool_restricted():
    code = "import os; print(os.name)"
    result = code_execution_tool.invoke({"code": code})
    assert result["success"] is False
    assert "ImportError" in result["error"] or "NameError" in result["error"] or "NotImplementedError" in result["error"]

def test_code_execution_tool_timeout():
    code = "while True: pass"
    result = code_execution_tool.invoke({"code": code})
    assert result["success"] is False
    assert "TimeoutError" in result["error"]
