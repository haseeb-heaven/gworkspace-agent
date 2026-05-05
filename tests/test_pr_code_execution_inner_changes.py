"""Tests for PR changes in gws_assistant/tools/code_execution_inner.py.

Covers:
- get_sandbox_globals: _safe_import allows whitelisted modules (csv, io, math, random)
- get_sandbox_globals: 'input' removed from dangerous builtins (instead of 'open')
- run_code: pre-processes import statements for whitelisted modules before exec
- run_code: uses standard compile() instead of compile_restricted
- _trim_output: still works as expected
"""
from __future__ import annotations

import base64

import pytest

# RestrictedPython is required for code_execution_inner.
# Skip in environments where it's not installed.
pytest.importorskip("RestrictedPython", reason="RestrictedPython not installed")

from gws_assistant.tools.code_execution_inner import (
    _trim_output,
    get_sandbox_globals,
    run_code,
)

# ---------------------------------------------------------------------------
# _trim_output
# ---------------------------------------------------------------------------

class TestTrimOutput:
    def test_short_string_unchanged(self):
        assert _trim_output("hello") == "hello"

    def test_exact_max_len_unchanged(self):
        text = "x" * 1000
        assert _trim_output(text) == text

    def test_long_string_truncated(self):
        text = "x" * 1500
        result = _trim_output(text)
        assert len(result) < 1500
        assert "[output truncated]" in result

    def test_truncated_at_1000_chars(self):
        text = "a" * 1001
        result = _trim_output(text)
        assert result == "a" * 1000 + "... [output truncated]"

    def test_custom_max_len(self):
        text = "hello world"
        result = _trim_output(text, max_len=5)
        assert result == "hello... [output truncated]"


# ---------------------------------------------------------------------------
# get_sandbox_globals — _safe_import allows whitelisted modules
# ---------------------------------------------------------------------------

class TestGetSandboxGlobalsImport:
    def test_sandbox_globals_has_builtins(self):
        g = get_sandbox_globals()
        assert "__builtins__" in g

    def test_safe_import_allows_csv(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        result = safe_import("csv")
        import csv
        assert result is csv

    def test_safe_import_allows_io(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        result = safe_import("io")
        import io
        assert result is io

    def test_safe_import_allows_math(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        result = safe_import("math")
        import math
        assert result is math

    def test_safe_import_allows_random(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        result = safe_import("random")
        import random
        assert result is random

    def test_safe_import_blocks_os(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        with pytest.raises(ImportError, match="disabled inside the code sandbox"):
            safe_import("os")

    def test_safe_import_blocks_subprocess(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        with pytest.raises(ImportError):
            safe_import("subprocess")

    def test_safe_import_blocks_sys(self):
        g = get_sandbox_globals()
        safe_import = g["__builtins__"]["__import__"]
        with pytest.raises(ImportError):
            safe_import("sys")

    def test_open_not_in_builtins(self):
        """PR change: 'open' removed from dangerous builtins."""
        g = get_sandbox_globals()
        assert "open" not in g["__builtins__"]

    def test_exec_not_in_builtins(self):
        g = get_sandbox_globals()
        assert "exec" not in g["__builtins__"]

    def test_eval_not_in_builtins(self):
        g = get_sandbox_globals()
        assert "eval" not in g["__builtins__"]

    def test_input_not_in_builtins(self):
        """PR change: 'input' is now removed from dangerous builtins."""
        g = get_sandbox_globals()
        assert "input" not in g["__builtins__"]


# ---------------------------------------------------------------------------
# get_sandbox_globals — whitelisted modules are pre-injected
# ---------------------------------------------------------------------------

class TestGetSandboxGlobalsModules:
    def test_csv_pre_injected(self):
        g = get_sandbox_globals()
        assert "csv" in g

    def test_io_pre_injected(self):
        g = get_sandbox_globals()
        assert "io" in g

    def test_math_pre_injected(self):
        g = get_sandbox_globals()
        assert "math" in g

    def test_random_pre_injected(self):
        g = get_sandbox_globals()
        assert "random" in g

    def test_guard_functions_present(self):
        g = get_sandbox_globals()
        assert "_getiter_" in g
        assert "_getitem_" in g
        assert "_getattr_" in g


# ---------------------------------------------------------------------------
# run_code — import preprocessing for whitelisted modules
# ---------------------------------------------------------------------------

def _b64(code: str) -> str:
    return base64.b64encode(code.encode("utf-8")).decode("ascii")


class TestRunCodeImportPreprocessing:
    def test_run_code_with_import_csv_stripped(self):
        """PR: 'import csv' is stripped before execution since csv is pre-injected."""
        code = "import csv\nresult = 'csv ok'"
        result = run_code(_b64(code))
        # Should succeed (import stripped, csv still available)
        assert result["success"] is True

    def test_run_code_with_import_math_stripped(self):
        code = "import math\nx = math.sqrt(4)\nprint(x)"
        result = run_code(_b64(code))
        assert result["success"] is True
        assert "2.0" in result["stdout"]

    def test_run_code_with_from_math_import_stripped(self):
        code = "from math import sqrt\nresult = sqrt(9)"
        result = run_code(_b64(code))
        assert result["success"] is True

    def test_run_code_basic_print(self):
        code = "print('hello world')"
        result = run_code(_b64(code))
        assert result["success"] is True
        assert "hello world" in result["stdout"]

    def test_run_code_invalid_base64(self):
        result = run_code("!!invalid_base64!!")
        assert result["success"] is False
        assert "Base64DecodingError" in (result["error"] or "")

    def test_run_code_syntax_error(self):
        code = "def foo(:\n    pass"
        result = run_code(_b64(code))
        assert result["success"] is False

    def test_run_code_arithmetic(self):
        code = "x = 2 + 2\nprint(x)"
        result = run_code(_b64(code))
        assert result["success"] is True
        assert "4" in result["stdout"]

    def test_run_code_list_comprehension_works_with_getiter_guard(self):
        """list comprehension requires _getiter_ guard in sandbox globals."""
        code = "result = [x**2 for x in range(5)]\nprint(result)"
        res = run_code(_b64(code))
        assert res["success"] is True  # passes only if _getiter_ is in sandbox_globals

    def test_run_code_output_truncated_for_large_output(self):
        code = "print('x' * 2000)"
        result = run_code(_b64(code))
        assert result["success"] is True
        assert "[output truncated]" in result["stdout"]


# ---------------------------------------------------------------------------
# run_code — regression: dangerous operations still blocked
# ---------------------------------------------------------------------------

class TestRunCodeSecurityRegressions:
    def test_blocked_os_import_via_import(self):
        """os should still be blocked from import."""
        code = "import os\nprint(os.getcwd())"
        result = run_code(_b64(code))
        assert result["success"] is False

    def test_blocked_subprocess(self):
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = run_code(_b64(code))
        assert result["success"] is False
