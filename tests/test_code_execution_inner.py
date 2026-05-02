import base64

from gws_assistant.tools.code_execution_inner import _trim_output, get_sandbox_globals, run_code


def test_trim_output():
    assert _trim_output("abc", 5) == "abc"  # nosec
    assert _trim_output("abcdefg", 5) == "abcde... [output truncated]"  # nosec

def test_get_sandbox_globals():
    globals_dict = get_sandbox_globals()
    assert "math" in globals_dict  # nosec
    assert "random" in globals_dict  # nosec
    assert "csv" in globals_dict  # nosec
    assert "open" not in globals_dict["__builtins__"]  # nosec

def test_run_code_success():
    code = "print('hello world'); x = 10; y = 20; result = x + y"
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    result = run_code(code_b64)
    assert result["success"] is True  # nosec
    assert "hello world" in result["stdout"]  # nosec

def test_run_code_error():
    code = "1 / 0"
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    result = run_code(code_b64)
    assert result["success"] is False  # nosec
    assert "ZeroDivisionError" in result["error"]  # nosec

def test_run_code_restricted():
    # Attempt to use a restricted builtin
    code = "import os"
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    result = run_code(code_b64)
    # RestrictedPython blocks imports by default unless in whitelist
    assert result["success"] is False  # nosec
    assert "ImportError" in result["error"] or "SyntaxError" in result["error"]  # nosec

def test_run_code_invalid_b64():
    result = run_code("invalid!!!")
    assert result["success"] is False  # nosec
    assert "Base64DecodingError" in result["error"]  # nosec
