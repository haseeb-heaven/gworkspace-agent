"""Inner RestrictedPython sandbox entrypoint.

Reads base64-encoded Python source from stdin and prints one JSON line.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import sys
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

# Allowed modules in the sandbox
import csv
import io
import math
import random

# CompileResult import removed: compile_restricted result is used directly as bytecode.
# Kept unused in prior versions; no longer needed after refactor to flat compile flow.
from RestrictedPython import compile_restricted, safe_builtins, safe_globals, utility_builtins
from RestrictedPython.Guards import full_write_guard, guarded_setattr, safer_getattr
from RestrictedPython.PrintCollector import PrintCollector

# Set up logger for the standalone script. Configure handler only when invoked
# as a subprocess entrypoint to avoid duplicating handlers on re-import (e.g., tests).
logger = logging.getLogger(__name__)
if __name__ == "__main__" and not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def get_sandbox_globals() -> dict[str, object]:
    """Build and return the restricted globals dictionary for the sandbox environment.

    Provides a safe set of builtins and overrides standard functions to prevent
    unauthorized file access or imports. Whitelists specific modules like 'math'.

    Returns:
        A dictionary containing the safe globals and builtins for RestrictedPython.
    """
    sandbox_globals = safe_globals.copy()
    sandbox_globals["__builtins__"] = safe_builtins.copy()
    sandbox_globals["__builtins__"].update(utility_builtins)

    for dangerous in ("open", "exec", "eval", "compile", "input"):
        sandbox_globals["__builtins__"].pop(dangerous, None)

    # Allow __import__ for whitelisted modules only
    def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        allowed_modules = {"csv", "io", "math", "random"}
        logger.debug("Import requested for '%s'", name)
        if name in allowed_modules:
            return __import__(name, *args, **kwargs)
        raise ImportError(f"Import of '{name}' is disabled inside the code sandbox.")

    sandbox_globals["__builtins__"]["__import__"] = _safe_import

    # Override RestrictedPython's import guard to allow whitelisted modules
    def _safe_getattr(obj: Any, name: str) -> Any:
        if name == "__import__":
            return _safe_import
        return safer_getattr(obj, name)

    # Runtime guards - if using standard compile(), these aren't auto-injected
    # but they are good to have if any restricted code is called.
    sandbox_globals["_getiter_"] = iter
    sandbox_globals["_getitem_"] = lambda obj, key: obj[key]
    sandbox_globals["_getattr_"] = _safe_getattr
    sandbox_globals["_setattr_"] = guarded_setattr
    sandbox_globals["_write_"] = full_write_guard
    sandbox_globals["_unpack_sequence_"] = lambda seq, length: list(seq)
    sandbox_globals["_iter_unpack_sequence_"] = lambda seq, length: list(seq)

    def _inplacevar(op: str, target: Any, expr: Any) -> Any:
        if op == "+=":
            target += expr
            return target
        if op == "-=":
            target -= expr
            return target
        if op == "*=":
            target *= expr
            return target
        if op == "/=":
            target /= expr
            return target
        if op == "//=":
            target //= expr
            return target
        if op == "%=":
            target %= expr
            return target
        if op == "**=":
            target **= expr
            return target
        if op == "&=":
            target &= expr
            return target
        if op == "|=":
            target |= expr
            return target
        if op == "^=":
            target ^= expr
            return target
        if op == "<<=":
            target <<= expr
            return target
        if op == ">>=":
            target >>= expr
            return target
        raise NotImplementedError(f"Unsupported in-place operator: {op}")

    sandbox_globals["_inplacevar_"] = _inplacevar

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
            logger.warning("Failed to set memory limit: %s", e)


def _trim_output(text: str, max_len: int = 1000) -> str:
    """Trim a string to a maximum length."""
    if len(text) > max_len:
        return text[:max_len] + "... [output truncated]"
    return text


def run_code(code_b64: str) -> dict[str, object]:
    """Execute base64-encoded Python code securely within a restricted sandbox.

    Decodes the provided base64 string, compiles it using RestrictedPython,
    and executes it with a restricted globals dictionary. Captures stdout/stderr.

    Args:
        code_b64: A base64-encoded string containing the Python source code.

    Returns:
        A dictionary containing execution results with keys: 'stdout',
        'stderr', 'success', and 'error'.

    Raises:
        Does not raise exceptions directly; instead, catches them and
        returns them in the 'error' field of the result dictionary.
    """
    result: dict[str, object] = {"stdout": "", "stderr": "", "success": False, "error": None}

    # 1. Base64 Decode
    try:
        code = base64.b64decode(code_b64.encode("ascii")).decode("utf-8")
    except Exception as exc:
        result["error"] = f"Base64DecodingError: {exc}"
        return result

    # 2. Setup Sandbox
    sandbox_globals = get_sandbox_globals()

    # 3. Compile
    try:
        byte_code = compile_restricted(code, filename="<string>", mode="exec")
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        return result

    # 4. Execute
    try:
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            # exec() in the restricted namespace
            exec(byte_code, sandbox_globals)

        # RestrictedPython's PrintCollector result
        printed = sandbox_globals.get("_print")
        if callable(printed):
            text = str(printed() or "")
            if text:
                result["stdout"] = text

        # Captured stdout/stderr
        buffer_text = output_buffer.getvalue()
        if buffer_text:
            if result["stdout"]:
                result["stdout"] = f"{result['stdout']}\n{buffer_text}"
            else:
                result["stdout"] = buffer_text

        result["stdout"] = _trim_output(str(result["stdout"]))
        result["success"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["stderr"] = _trim_output(str(exc))

    return result


if __name__ == "__main__":
    set_memory_limit()
    payload = run_code(sys.stdin.read().strip())
    print(json.dumps(payload))
