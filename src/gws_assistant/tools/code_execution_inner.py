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
    resource = None

from RestrictedPython import compile_restricted, safe_builtins, safe_globals, utility_builtins
from RestrictedPython.Guards import full_write_guard, guarded_setattr, safer_getattr
from RestrictedPython.PrintCollector import PrintCollector

# Allowed modules in the sandbox
import csv
import math
import random

def get_sandbox_globals() -> dict[str, object]:
    sandbox_globals = safe_globals.copy()
    sandbox_globals["__builtins__"] = safe_builtins.copy()
    sandbox_globals["__builtins__"].update(utility_builtins)

    for dangerous in ("open", "exec", "eval", "compile", "input", "__import__"):
        sandbox_globals["__builtins__"].pop(dangerous, None)

    sandbox_globals["_getiter_"] = iter
    sandbox_globals["_getitem_"] = lambda obj, key: obj[key]
    sandbox_globals["_getattr_"] = safer_getattr
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
        limit = 256 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ValueError, OSError):
            pass


def _trim_output(text: str, max_len: int = 1000) -> str:
    """Trim a string to a maximum length."""
    if len(text) > max_len:
        return text[:max_len] + "... [output truncated]"
    return text


def run_code(code_b64: str) -> dict[str, object]:
    result: dict[str, object] = {"stdout": "", "stderr": "", "success": False, "error": None}

    try:
        code = base64.b64decode(code_b64.encode("ascii")).decode("utf-8")
    except Exception as exc:
        result["error"] = f"Base64DecodingError: {exc}"
        return result

    sandbox_globals = get_sandbox_globals()
    set_memory_limit()

    try:
        byte_code = compile_restricted(code, filename="<string>", mode="exec")
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
    payload = run_code(sys.stdin.read().strip())
    print(json.dumps(payload))
