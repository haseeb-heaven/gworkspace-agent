"""Code execution tool for the LangChain agent.

Uses a thread-based sandbox with a hard timeout instead of multiprocessing
so it works reliably on Windows (where 'spawn' start-method causes issues
inside virtualenvs / pytest sessions).
"""

from __future__ import annotations

import ast
import contextlib
import datetime
import io
import json
import math
import re
import threading
import time
from typing import Any

from langchain_core.tools import tool
from RestrictedPython import compile_restricted, safe_builtins, safe_globals, utility_builtins

from gws_assistant.models import CodeExecutionResult, StructuredToolResult

_DEFAULT_TIMEOUT_SECONDS = 5
_BANNED_PATTERNS = [
    r"\bos\.remove\b",
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bsocket\b",
    r"\bopen\(",
    r"__import__",
    r"\brequests\b",
    r"\burllib\b",
]


# Safe stdlib modules that the LLM commonly needs for numeric/currency/date work.
# These are pre-injected into the sandbox globals so LLM-generated `import X`
# statements can be stripped without breaking the computation.
_SAFE_MODULES: dict[str, Any] = {
    "math": math,
    "re": re,
    "json": json,
    "datetime": datetime,
    "time": time,
}


def _sanitize_llm_code(code: str) -> str:
    """Strip top-level import statements from LLM-generated code.

    RestrictedPython blocks ALL imports via _restricted_import(). The LLM
    frequently emits `import math` / `import re` / `import json` for simple
    numeric tasks. Rather than fail at runtime we:
      1. Remove the import line entirely (the module is pre-injected as a
         sandbox global, so the name is still available in the namespace).
      2. Leave all other lines untouched.

    This is intentionally conservative: only bare `import X` and
    `from X import Y` lines at the start of a physical line are removed.
    """
    cleaned_lines: list[str] = []
    _SAFE_NAMES = set(_SAFE_MODULES.keys())
    for line in code.splitlines():
        stripped = line.lstrip()
        is_safe_import = False
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Check if this import targets a safe module we pre-injected.
            # Example: "import math", "from json import loads"
            words = stripped.split()
            if len(words) >= 2:
                # for "import x", words[1] is x
                # for "from x import y", words[1] is x
                mod_name = words[1].split(".")[0]
                if mod_name in _SAFE_NAMES:
                    is_safe_import = True

        if is_safe_import:
            # Keep the line as a comment so line numbers stay stable for
            # error messages, but neutralise the import.
            cleaned_lines.append("# [sandbox-stripped] " + line)
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def get_safe_globals() -> dict[str, Any]:
    safe_g = safe_globals.copy()
    safe_g["__builtins__"] = safe_builtins.copy()
    safe_g["__builtins__"].update(utility_builtins)
    safe_g["__builtins__"]["__import__"] = _restricted_import
    safe_g["__builtins__"]["sum"] = sum
    safe_g["__builtins__"]["list"] = list
    safe_g["__builtins__"]["dict"] = dict
    safe_g["__builtins__"]["range"] = range
    safe_g["__builtins__"]["int"] = int
    safe_g["__builtins__"]["str"] = str
    safe_g["__builtins__"]["float"] = float
    safe_g["__builtins__"]["bool"] = bool
    safe_g["__builtins__"]["len"] = len
    safe_g["__builtins__"]["abs"] = abs
    safe_g["__builtins__"]["min"] = min
    safe_g["__builtins__"]["max"] = max
    safe_g["__builtins__"]["round"] = round
    safe_g["__builtins__"]["reversed"] = reversed
    safe_g["__builtins__"]["sorted"] = sorted
    safe_g["__builtins__"]["enumerate"] = enumerate
    safe_g["__builtins__"]["zip"] = zip
    safe_g["__builtins__"]["map"] = map
    safe_g["__builtins__"]["filter"] = filter

    # Simple object that has a write method to satisfy RestrictedPython print()
    class SimpleCollector:
        def __init__(self, _getattr_=None):
            self.txt = []
            self._getattr_ = _getattr_

        def write(self, text):
            self.txt.append(text)

        def __call__(self):
            return "".join(self.txt).strip()

        def _call_print(self, *args, **kwargs):
            import builtins

            if kwargs.get("file", None) is None:
                kwargs["file"] = self
            builtins.print(*args, **kwargs)

    collector = SimpleCollector()

    def _print_factory(_getattr_=None):
        collector._getattr_ = _getattr_
        return collector

    safe_g["_print_"] = _print_factory
    safe_g["_print_buffer_instance"] = collector

    from RestrictedPython.Guards import safer_getattr

    def safe_setattr(obj, name, value):
        if name.startswith("_"):
            raise AttributeError(f'"{name}" is an invalid attribute name because it starts with "_"')
        return setattr(obj, name, value)

    safe_g["_getattr_"] = safer_getattr
    safe_g["_setattr_"] = safe_setattr
    safe_g["__builtins__"]["getattr"] = safer_getattr
    safe_g["__builtins__"]["setattr"] = safe_setattr

    safe_g["_getiter_"] = iter
    safe_g["_getitem_"] = lambda obj, key: obj[key]
    safe_g["_write_"] = lambda obj: obj
    safe_g["_unpack_sequence_"] = lambda seq, length, _getiter=iter: list(seq)
    safe_g["_iter_unpack_sequence_"] = lambda seq, length, _getiter=iter: list(seq)

    def _inplacevar(op, target, expr):
        if op == "+=":
            return target + expr
        if op == "-=":
            return target - expr
        if op == "*=":
            return target * expr
        if op == "/=":
            return target / expr
        if op == "//=":
            return target // expr
        if op == "%=":
            return target % expr
        if op == "**=":
            return target ** expr
        if op == "&=":
            return target & expr
        if op == "|=":
            return target | expr
        if op == "^=":
            return target ^ expr
        if op == "<<=":
            return target << expr
        if op == ">>=":
            return target >> expr
        raise NotImplementedError(f"Unsupported in-place operator: {op}")

    safe_g["_inplacevar_"] = _inplacevar
    # Pre-inject safe stdlib modules so stripped imports still resolve.
    safe_g.update(_SAFE_MODULES)

    # Pre-inject common datetime classes for AI robustness
    safe_g["datetime"] = datetime.datetime
    safe_g["date"] = datetime.date
    safe_g["timedelta"] = datetime.timedelta
    safe_g["now"] = datetime.datetime.now()

    # AI Robustness: Pre-inject common lowercase aliases often emitted by LLMs
    safe_g["true"] = True
    safe_g["false"] = False
    safe_g["null"] = None
    safe_g["quote"] = lambda x: json.dumps(x, ensure_ascii=True)

    return safe_g


def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in _SAFE_MODULES:
        return _SAFE_MODULES[name]
    raise ImportError(f"Import of '{name}' is disabled inside the code sandbox.")


def _validate_submitted_code(code: str, timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS) -> str | None:
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
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            return f"TimeoutError: Execution exceeded {timeout_seconds} seconds."
    return None


def _run_in_thread_sandbox(
    code: str, result_holder: list[CodeExecutionResult], extra_globals: dict | None = None
) -> None:
    """Execute *code* inside RestrictedPython, storing a CodeExecutionResult in result_holder[0]."""
    exec_result = CodeExecutionResult(code=code)
    try:
        # Strip import statements before compilation — the sandbox forbids them
        # but pre-injects the most common modules (math, re, json) as globals.
        sanitized = _sanitize_llm_code(code)
        byte_code = compile_restricted(sanitized, filename="<string>", mode="exec")
        sandbox_globals = get_safe_globals()

        # Inject extra context (e.g. task_results) into the sandbox globals
        if extra_globals:
            sandbox_globals.update(extra_globals)

        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            exec(byte_code, sandbox_globals)  # noqa: S102

        # Capture both _print_ (RestrictedPython internal) and direct stdout
        if "_print_buffer_instance" in sandbox_globals:
            collector = sandbox_globals["_print_buffer_instance"]
            if callable(collector):
                exec_result.stdout = str(collector())

        buffer_val = output_buffer.getvalue()
        if buffer_val:
            exec_result.stdout = (
                f"{exec_result.stdout}\n{buffer_val}".strip() if exec_result.stdout else buffer_val.strip()
            )

        # --- PARSE RETURN VALUE ---
        # 1. Best case: user explicitly assigned to 'result'
        if "result" in sandbox_globals:
            exec_result.return_value = sandbox_globals["result"]

        # 2. Next best: parse the last line of stdout as a Python literal
        elif exec_result.stdout:
            try:
                last_line = exec_result.stdout.strip().splitlines()[-1]
                exec_result.return_value = ast.literal_eval(last_line)
            except (SyntaxError, ValueError):
                # Fallback if stdout is not a literal
                exec_result.return_value = exec_result.stdout

        # 3. Fallback: capture all variables from sandbox_globals
        else:

            def is_json_serializable(v):
                return isinstance(v, (str, int, float, bool, list, dict, type(None)))

            results_vars = {
                k: v
                for k, v in sandbox_globals.items()
                if not k.startswith("_")
                and k != "__builtins__"
                and not callable(v)
                and k not in _SAFE_MODULES
                and is_json_serializable(v)
            }
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


def execute_generated_code(code: str, config=None, extra_globals: dict[str, Any] | None = None) -> StructuredToolResult:
    code = re.sub(r"\\\s*$", "", code, flags=re.MULTILINE)
    timeout_seconds = (
        int(getattr(config, "code_execution_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
        if config is not None
        else _DEFAULT_TIMEOUT_SECONDS
    )
    validation_error = _validate_submitted_code(code, timeout_seconds=timeout_seconds)
    if validation_error and "SyntaxError" in validation_error and ";" in code:
        # AI Robustness: Many LLMs (especially on Groq/OpenRouter) tend to emit 
        # "one-liners" with semicolons that break Python's block syntax.
        # We try to expand them into multi-line code and re-validate.
        # This is a heuristic: split by semicolon followed by space.
        fixed_code = code.replace("; ", "\n").replace(";", "\n")
        second_validation = _validate_submitted_code(fixed_code, timeout_seconds=timeout_seconds)
        if not second_validation:
            from gws_assistant.logging_utils import get_logger
            get_logger(__name__).info("AI Robustness: Auto-fixed semicolon syntax in one-liner code block.")
            code = fixed_code
            validation_error = None

    if validation_error:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=validation_error,
        )

    if config and getattr(config, "code_execution_backend", None) == "e2b" and getattr(config, "e2b_api_key", None):
        return _execute_e2b(code, config.e2b_api_key)

    result_holder: list[CodeExecutionResult] = []
    thread = threading.Thread(target=_run_in_thread_sandbox, args=(code, result_holder, extra_globals), daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=f"TimeoutError: Execution exceeded {timeout_seconds} seconds.",
        )

    if not result_holder:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error="ProcessError: Sandbox thread finished without returning a result.",
        )

    return normalize_code_result(result_holder[0])


def code_execution_tool_with_config(config, logger: Any):
    """Factory to create a config-aware code execution tool for LangChain."""

    @tool
    def code_execution_tool(code: str) -> dict[str, Any]:
        """Execute Python in a restricted sandbox or cloud (E2B) with normalized results.

        CRITICAL: Use the pre-injected 'quote(value)' helper for all strings to avoid syntax errors
        with nested quotes or special characters. Example: name = quote("O'Reilly")
        """
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
