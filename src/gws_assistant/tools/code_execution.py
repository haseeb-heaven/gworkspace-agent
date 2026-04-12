"""Code execution tool for the LangChain agent.

Uses a thread-based sandbox with a hard timeout instead of multiprocessing
so it works reliably on Windows (where 'spawn' start-method causes issues
inside virtualenvs / pytest sessions).
"""

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
    def _inplacevar(op, target, expr):
        if op == '+=': return target + expr
        if op == '-=': return target - expr
        if op == '*=': return target * expr
        if op == '/=': return target / expr
        return expr
    safe_g["_inplacevar_"] = _inplacevar
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


def _run_in_thread_sandbox(code: str, result_holder: list[CodeExecutionResult]) -> None:
    """Execute *code* inside RestrictedPython, storing a CodeExecutionResult in result_holder[0]."""
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
            exec_result.stdout = f"{exec_result.stdout}\n{buffer_val}".strip() if exec_result.stdout else buffer_val.strip()

        # Capture all variables from sandbox_globals except builtins/internals
        results_vars = {
            k: v for k, v in sandbox_globals.items()
            if not k.startswith("_") and k != "__builtins__" and not callable(v)
        }
        # If the code assigned a top-level `result` variable, expose that directly
        # as return_value so that parsed_value == result (not a dict containing both
        # "result" and "_result" keys, which violates the structured contract).
        if "result" in sandbox_globals:
            exec_result.return_value = sandbox_globals["result"]
        else:
            exec_result.return_value = results_vars
        exec_result.success = True
    except Exception as exc:
        exec_result.success = False
        exec_result.error = f"{type(exc).__name__}: {exc}"
    result_holder.append(exec_result)


def normalize_code_result(result: CodeExecutionResult) -> StructuredToolResult:
    output = {
        "code": result.code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "parsed_value": result.return_value,
    }
    # Flatten variables into top-level for easier placeholder and verification access
    if isinstance(result.return_value, dict):
        output.update(result.return_value)

    return StructuredToolResult(
        success=result.success,
        output=output,
        error=result.error,
    )


def _execute_e2b(code: str, api_key: str) -> StructuredToolResult:
    """Execute code in an E2B cloud sandbox using the latest Sandbox API."""
    try:
        from e2b_code_interpreter import Sandbox
        # Sandbox.create() uses E2B_API_KEY env var if api_key is not passed or if configured globally.
        # We pass it explicitly to be sure.
        with Sandbox.create(api_key=api_key) as sandbox:
            execution = sandbox.run_code(code)
            
            stdout = "\n".join(str(log.text) if hasattr(log, "text") else str(log) for log in execution.logs.stdout)
            stderr = "\n".join(str(log.text) if hasattr(log, "text") else str(log) for log in execution.logs.stderr)
            
            if execution.error:
                return StructuredToolResult(
                    success=False,
                    output={"code": code, "stdout": stdout, "stderr": stderr, "parsed_value": None},
                    error=f"E2BError: {execution.error.name}: {execution.error.value}",
                )
            
            return StructuredToolResult(
                success=True,
                output={"code": code, "stdout": stdout, "stderr": stderr, "parsed_value": execution.text},
                error=None,
            )
    except Exception as exc:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=f"E2BExecutionError: {exc}",
        )


def execute_generated_code(code: str, config: AppConfigModel | None = None) -> StructuredToolResult:
    validation_error = _validate_submitted_code(code)
    if validation_error:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=validation_error,
        )

    # Dispatch to E2B if configured and key is present
    if config and config.code_execution_backend == "e2b" and config.e2b_api_key:
        return _execute_e2b(code, config.e2b_api_key)

    # Default to local RestrictedPython
    result_holder: list[CodeExecutionResult] = []
    thread = threading.Thread(target=_run_in_thread_sandbox, args=(code, result_holder), daemon=True)
    thread.start()
    thread.join(timeout=_TIMEOUT_SECONDS)

    if thread.is_alive():
        # Thread is stuck (infinite loop etc.) — we cannot truly kill it, but we report timeout.
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=f"TimeoutError: Execution exceeded {_TIMEOUT_SECONDS} seconds.",
        )

    if not result_holder:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error="ProcessError: Sandbox thread finished without returning a result.",
        )

    return normalize_code_result(result_holder[0])


def code_execution_tool_with_config(config: AppConfigModel, logger: Any):
    """Factory to create a config-aware code execution tool for LangChain."""
    @tool
    def code_execution_tool(code: str) -> dict[str, Any]:
        """Execute Python in a restricted sandbox or cloud (E2B) with normalized results."""
        structured = execute_generated_code(code, config=config)
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
    return code_execution_tool


@tool
def code_execution_tool(code: str) -> dict[str, Any]:
    """Execute Python in a restricted local sandbox (Backward compatibility)."""
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
