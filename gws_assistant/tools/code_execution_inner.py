"""Inner RestrictedPython sandbox entrypoint.

Reads base64-encoded Python source from stdin and prints one JSON line.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import sys

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

# Allowed modules in the sandbox
import csv
import math
import random

from RestrictedPython import compile_restricted, safe_builtins, safe_globals, utility_builtins
from RestrictedPython.Guards import full_write_guard, guarded_setattr, safer_getattr
from RestrictedPython.PrintCollector import PrintCollector


def get_sandbox_globals() -> dict[str, object]:
    sandbox_globals = safe_globals.copy()
    sandbox_globals["__builtins__"] = safe_builtins.copy()
    sandbox_globals["__builtins__"].update(utility_builtins)

    for dangerous in ("open", "exec", "eval", "compile", "input"):
        sandbox_globals["__builtins__"].pop(dangerous, None)

    # Allow __import__ for whitelisted modules only
    def _safe_import(name, *args, **kwargs):
        allowed_modules = {"csv", "io", "math", "random"}
        # Debug: log import attempts
        import sys
        print(f"DEBUG: Import requested for '{name}'", file=sys.stderr)
        if name in allowed_modules:
            return __import__(name, *args, **kwargs)
        raise ImportError(f"Import of '{name}' is disabled inside the code sandbox.")

    sandbox_globals["__builtins__"]["__import__"] = _safe_import

    # Override RestrictedPython's import guard to allow whitelisted modules
    def _safe_getattr(object, name):
        if name == "__import__":
            return _safe_import
        return safer_getattr(object, name)

    sandbox_globals["_getiter_"] = iter
    sandbox_globals["_getitem_"] = lambda obj, key: obj[key]
    sandbox_globals["_getattr_"] = _safe_getattr
    sandbox_globals["_setattr_"] = guarded_setattr
    sandbox_globals["_write_"] = full_write_guard
    sandbox_globals["_print_"] = PrintCollector

    # Whitelist allowed modules
    sandbox_globals["csv"] = csv
    sandbox_globals["io"] = io
    sandbox_globals["math"] = math
    sandbox_globals["random"] = random
    return sandbox_globals


def set_memory_limit() -> None:
    """Limit the memory usage of the process on systems that support it."""
    if resource:
        # Limit to 256MB
        limit_bytes = 256 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))  # type: ignore[attr-defined]
        except (ValueError, OSError) as e:
            print(f"DEBUG: Failed to set memory limit: {e}", file=sys.stderr)


def _trim_output(text: str, max_len: int = 1000) -> str:
    """Trim a string to a maximum length."""
    if len(text) > max_len:
        return text[:max_len] + "... [output truncated]"
    return text


def run_code(code_b64: str) -> dict[str, object]:
    result: dict[str, object] = {"stdout": "", "stderr": "", "success": False, "error": None}

    try:
        try:
            code = base64.b64decode(code_b64.encode("ascii")).decode("utf-8")
        except Exception as exc:
            result["error"] = f"Base64DecodingError: {exc}"
            return result

        # Imports are handled by _safe_import in get_sandbox_globals
        sandbox_globals = get_sandbox_globals()

        # Use compile_restricted for security.
        try:
            byte_code = compile_restricted(code, filename="<string>", mode="exec")
        except SyntaxError as e:
            result["error"] = f"SyntaxError: {e}"
            return result

        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            exec(byte_code, sandbox_globals)

        printed = sandbox_globals.get("_print")
        if callable(printed):
            text = str(printed() or "")
            if text:
                result["stdout"] = text

        buffer_text = output_buffer.getvalue()
        if buffer_text:
            if result["stdout"]:
                result["stdout"] = f"{result['stdout']}\n{buffer_text}"
            else:
                result["stdout"] = buffer_text

        result["stdout"] = _trim_output(str(result["stdout"]))
        result["success"] = True
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["stderr"] = _trim_output(str(exc))
        return result


if __name__ == "__main__":
    set_memory_limit()
    payload = run_code(sys.stdin.read().strip())
    print(json.dumps(payload))
