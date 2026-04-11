"""Code execution tool for the LangChain agent."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import threading
from typing import Any

from RestrictedPython import compile_restricted, safe_builtins, safe_globals, utility_builtins
from RestrictedPython.PrintCollector import PrintCollector
from langchain_core.tools import tool

from gws_assistant.models import CodeExecutionResult, StructuredToolResult

_TIMEOUT_SECONDS = 5
_BANNED_PATTERNS = [
    r"\bimport\s+__future__\b",
    r"\bos\.remove\b",
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bsocket\b",
    r"\bopen\(",
    r"__import__",
]


def get_safe_globals() -> dict[str, Any]:
    safe_g = safe_globals.copy()
    safe_g["__builtins__"] = safe_builtins.copy()
    safe_g["__builtins__"].update(utility_builtins)
    safe_g["__builtins__"]["__import__"] = _restricted_import
    safe_g["_print_"] = PrintCollector
    safe_g["_getattr_"] = getattr
    safe_g["_setattr_"] = setattr
    safe_g["_getiter_"] = iter
    safe_g["_getitem_"] = lambda obj, key: obj[key]
    safe_g["_write_"] = lambda obj: obj
    return safe_g


def _restricted_import(*_: Any, **__: Any) -> None:
    raise ImportError("Imports are disabled inside the code sandbox.")


def _validate_submitted_code(code: str) -> str | None:
    for pattern in _BANNED_PATTERNS:
        if re.search(pattern, code):
            return f"SecurityError: disallowed pattern matched: {pattern}"
    try:
        ast.parse(code)
    except Exception as exc:
        return f"SyntaxError: {exc}"
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            return "SecurityError: import __future__ is blocked."
    return None


def _run_in_thread(code: str, result_holder: list) -> None:
    """Execute sandboxed code in the current thread and store a CodeExecutionResult in result_holder[0]."""
    exec_result = CodeExecutionResult(code=code)
    try:
        byte_code = compile_restricted(code, filename="<string>", mode="exec")
        sandbox_globals = get_safe_globals()
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            exec(byte_code, sandbox_globals)  # noqa: S102

        if "_print" in sandbox_globals:
            exec_result.stdout = sandbox_globals["_print"]()
        buffer_val = output_buffer.getvalue()
        if buffer_val:
            exec_result.stdout = f"{exec_result.stdout}\n{buffer_val}".strip()

        exec_result.return_value = sandbox_globals.get("result")
        exec_result.success = True
    except Exception as exc:
        exec_result.success = False
        exec_result.error = f"{type(exc).__name__}: {exc}"

    result_holder.append(exec_result)


def normalize_code_result(result: CodeExecutionResult) -> StructuredToolResult:
    return StructuredToolResult(
        success=result.success,
        output={
            "code": result.code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "parsed_value": result.return_value,
        },
        error=result.error,
    )


def execute_generated_code(code: str) -> StructuredToolResult:
    validation_error = _validate_submitted_code(code)
    if validation_error:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=validation_error,
        )

    result_holder: list = []
    thread = threading.Thread(target=_run_in_thread, args=(code, result_holder), daemon=True)
    thread.start()
    thread.join(timeout=_TIMEOUT_SECONDS)

    if thread.is_alive():
        # Thread is still running after timeout — treat as timeout (daemon thread will be GC'd)
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=f"TimeoutError: Execution exceeded {_TIMEOUT_SECONDS} seconds.",
        )

    if not result_holder:
        result = CodeExecutionResult(
            code=code,
            success=False,
            error="ProcessError: Sandbox thread finished without returning results.",
        )
    else:
        result = result_holder[0]

    return normalize_code_result(result)


@tool
def code_execution_tool(code: str) -> dict[str, Any]:
    """Execute Python in a restricted sandbox with normalized structured results."""
    structured = execute_generated_code(code)
    output = structured["output"] if isinstance(structured["output"], dict) else {}
    return {
        "success": structured["success"],
        "output": output,
        "error": structured["error"],
        "code": output.get("code", code),
        "stdout": output.get("stdout", ""),
        "stderr": output.get("stderr", ""),
        "parsed_value": output.get("parsed_value"),
    }
