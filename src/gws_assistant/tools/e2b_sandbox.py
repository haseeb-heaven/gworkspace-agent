"""E2B cloud sandbox execution backend for the LangChain agent."""

from __future__ import annotations

from typing import Any

from gws_assistant.models import StructuredToolResult

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    Sandbox = None  # type: ignore[assignment,misc]


def execute_with_e2b(code: str, api_key: str, timeout: int = 30) -> StructuredToolResult:
    """Execute Python code securely in an E2B cloud sandbox.

    Args:
        code: Python source to execute.
        api_key: E2B API key.
        timeout: Maximum execution time in seconds.

    Returns:
        StructuredToolResult with stdout, stderr, and parsed_value.
    """
    if Sandbox is None:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=(
                "E2B is not installed. Run: pip install e2b-code-interpreter"
            ),
        )

    try:
        with Sandbox(api_key=api_key, timeout=timeout) as sbx:
            execution = sbx.run_code(code)

            stdout = "\n".join(execution.logs.stdout).strip()
            stderr = "\n".join(execution.logs.stderr).strip()

            # Attempt to extract structured return value from the last result
            parsed_value: Any = None
            if execution.results:
                last = execution.results[-1]
                # e2b results expose .value (Python repr) and .json (str)
                try:
                    import json as _json
                    parsed_value = _json.loads(last.json) if last.json else last.value
                except Exception:
                    parsed_value = str(last.value) if last.value is not None else None

            if execution.error:
                return StructuredToolResult(
                    success=False,
                    output={"code": code, "stdout": stdout, "stderr": stderr, "parsed_value": parsed_value},
                    error=f"{execution.error.name}: {execution.error.value}",
                )

            return StructuredToolResult(
                success=True,
                output={"code": code, "stdout": stdout, "stderr": stderr, "parsed_value": parsed_value},
                error=None,
            )

    except Exception as exc:
        return StructuredToolResult(
            success=False,
            output={"code": code, "stdout": "", "stderr": "", "parsed_value": None},
            error=f"E2BError: {exc}",
        )
