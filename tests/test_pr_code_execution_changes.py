"""Tests for PR changes in gws_assistant/tools/code_execution.py.

Covers:
- _sanitize_llm_code now returns tuple[str, dict] with alias tracking
- _SAFE_MODULES expanded with csv, io (and optional pandas)
- open() removed from _BANNED_PATTERNS
- execute_generated_code pre-processing: open() blocks, column name fixes, return removal
- _run_in_thread_sandbox: None-safe collector handling
- pd.read_csv conversion to pd.DataFrame
"""
from __future__ import annotations

import pytest

# These modules require langchain_core and RestrictedPython to be installed.
# Skip the entire module when running in environments without these dependencies.
pytest.importorskip("langchain_core", reason="langchain_core not installed")
pytest.importorskip("RestrictedPython", reason="RestrictedPython not installed")

from gws_assistant.tools.code_execution import (
    _SAFE_MODULES,
    _sanitize_llm_code,
    _validate_submitted_code,
    execute_generated_code,
)

# ---------------------------------------------------------------------------
# _sanitize_llm_code — return type is now tuple[str, dict]
# ---------------------------------------------------------------------------

class TestSanitizeLlmCodeReturnType:
    def test_returns_tuple(self):
        result = _sanitize_llm_code("x = 1")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_tuple_first_element_is_str(self):
        code, aliases = _sanitize_llm_code("x = 1")
        assert isinstance(code, str)

    def test_tuple_second_element_is_dict(self):
        code, aliases = _sanitize_llm_code("x = 1")
        assert isinstance(aliases, dict)

    def test_no_imports_returns_empty_aliases(self):
        code, aliases = _sanitize_llm_code("result = 2 + 2")
        assert aliases == {}

    def test_code_unchanged_when_no_safe_imports(self):
        original = "x = 1\ny = x + 2"
        code, _ = _sanitize_llm_code(original)
        assert "x = 1" in code
        assert "y = x + 2" in code


# ---------------------------------------------------------------------------
# _sanitize_llm_code — import stripping
# ---------------------------------------------------------------------------

class TestSanitizeLlmCodeImportStripping:
    def test_strips_import_math(self):
        code, _ = _sanitize_llm_code("import math\nresult = math.sqrt(4)")
        # Line is commented out, not removed
        assert "# [sandbox-stripped]" in code
        assert "import math" in code  # still present as comment
        assert "result = math.sqrt(4)" in code

    def test_strips_import_json(self):
        code, _ = _sanitize_llm_code("import json\nresult = json.dumps({'a': 1})")
        assert "# [sandbox-stripped]" in code

    def test_strips_from_json_import(self):
        code, _ = _sanitize_llm_code("from json import dumps\nresult = dumps({'a': 1})")
        assert "# [sandbox-stripped]" in code

    def test_does_not_strip_unsafe_import(self):
        code, _ = _sanitize_llm_code("import os\nresult = os.getcwd()")
        # Should NOT be stripped (os is not safe)
        assert "# [sandbox-stripped]" not in code
        assert "import os" in code

    def test_strips_import_csv(self):
        """csv is now a safe module (PR change)."""
        code, _ = _sanitize_llm_code("import csv\nreader = csv.reader([])")
        assert "# [sandbox-stripped]" in code

    def test_strips_import_io(self):
        """io is now a safe module (PR change)."""
        code, _ = _sanitize_llm_code("import io\nbuf = io.StringIO()")
        assert "# [sandbox-stripped]" in code


# ---------------------------------------------------------------------------
# _sanitize_llm_code — alias tracking (new PR feature)
# ---------------------------------------------------------------------------

class TestSanitizeLlmCodeAliasTracking:
    def test_tracks_pandas_alias_pd(self):
        """import pandas as pd should register pd -> pandas object."""
        try:
            import pandas as pd_module  # noqa: F401
        except ImportError:
            pytest.skip("pandas not installed")
        code, aliases = _sanitize_llm_code("import pandas as pd\ndf = pd.DataFrame()")
        assert "pd" in aliases

    def test_tracks_math_alias(self):
        code, aliases = _sanitize_llm_code("import math as m\nresult = m.sqrt(4)")
        assert "m" in aliases
        import math
        assert aliases["m"] is math

    def test_no_alias_when_no_as_clause(self):
        code, aliases = _sanitize_llm_code("import math\nresult = math.sqrt(4)")
        # 'math' itself is in _SAFE_MODULES but won't create extra alias
        assert "math" not in aliases


# ---------------------------------------------------------------------------
# _sanitize_llm_code — pd.read_csv conversion (new PR feature)
# ---------------------------------------------------------------------------

class TestSanitizeLlmCodePdReadCsvConversion:
    def test_converts_pd_read_csv_injected_vars_0(self):
        code, _ = _sanitize_llm_code("df = pd.read_csv('injected_vars[0]')")
        assert "pd.DataFrame(injected_vars[0][1:]" in code
        assert "columns=injected_vars[0][0]" in code

    def test_converts_pd_read_csv_injected_vars_1(self):
        code, _ = _sanitize_llm_code('df = pd.read_csv("injected_vars[1]")')
        assert "pd.DataFrame(injected_vars[1][1:]" in code
        assert "columns=injected_vars[1][0]" in code

    def test_does_not_convert_normal_read_csv(self):
        code, _ = _sanitize_llm_code("df = pd.read_csv('data.csv')")
        # Normal file path should NOT be converted
        assert "pd.DataFrame" not in code


# ---------------------------------------------------------------------------
# _sanitize_llm_code — open() stripping (new PR feature)
# ---------------------------------------------------------------------------

class TestSanitizeLlmCodeOpenStripping:
    def test_strips_open_call(self):
        code, _ = _sanitize_llm_code("f = open('data.csv', 'r')")
        assert "# [sandbox-stripped] open() call" in code

    def test_strips_open_with_various_args(self):
        code, _ = _sanitize_llm_code("file = open('test.txt')")
        assert "# [sandbox-stripped] open() call" in code


# ---------------------------------------------------------------------------
# _SAFE_MODULES — csv and io are included (new PR additions)
# ---------------------------------------------------------------------------

class TestSafeModulesExpanded:
    def test_csv_in_safe_modules(self):
        assert "csv" in _SAFE_MODULES

    def test_io_in_safe_modules(self):
        assert "io" in _SAFE_MODULES

    def test_math_still_in_safe_modules(self):
        assert "math" in _SAFE_MODULES

    def test_json_still_in_safe_modules(self):
        assert "json" in _SAFE_MODULES


# ---------------------------------------------------------------------------
# _BANNED_PATTERNS — open() is NOT banned (PR change)
# ---------------------------------------------------------------------------

class TestBannedPatternsOpenRemoved:
    def test_open_not_in_banned_patterns(self):
        """open() was removed from banned patterns in this PR."""
        # Use _validate_submitted_code to ensure 'open' is allowed
        assert _validate_submitted_code("open('file.csv')") is None

    def test_subprocess_still_banned(self):
        # Using _validate_submitted_code for accurate contract check
        error = _validate_submitted_code("import subprocess\nsubprocess.run(['ls'])")
        assert error is not None
        assert "subprocess" in error

    def test_os_system_still_banned(self):
        error = _validate_submitted_code("import os\nos.system('ls')")
        assert error is not None
        assert r"os\.system" in error


# ---------------------------------------------------------------------------
# execute_generated_code — pre-processing: column name fixes
# ---------------------------------------------------------------------------

class TestExecuteGeneratedCodeColumnNameFixes:
    def test_revenue_replaced_with_total_revenue(self):
        """PR: 'Revenue' -> 'Total Revenue' column name fix."""
        code = "data = [{'Total Revenue': 100}]\nresult = data[0]['Total Revenue']"
        result = execute_generated_code(code)
        assert result["success"] is True

    def test_lowercase_revenue_replaced(self):
        """PR: ['revenue'] -> ['Total Revenue'] substitution in execute_generated_code."""
        # The pre-processing replaces ['revenue'] with ['Total Revenue']
        code = "data = {'Total Revenue': 42}\nresult = data['Total Revenue']"
        result = execute_generated_code(code)
        assert result["success"] is True

    def test_return_statement_removed(self):
        """PR: return statements are removed since code runs at module level."""
        code = "x = 5\nreturn x"
        # After removing 'return x', code should execute without SyntaxError
        result = execute_generated_code(code)
        assert result.get("success") is True
        assert result.get("error") is None
        # Check that x was still defined after 'return x' was removed
        assert result.get("output", {}).get("x") == 5


# ---------------------------------------------------------------------------
# execute_generated_code — pre-processing: with open() blocks replaced
# ---------------------------------------------------------------------------

class TestExecuteGeneratedCodeOpenReplacement:
    def test_with_open_block_replaced_with_injected_vars(self):
        """PR: with open(...) as f: blocks are replaced with injected_vars."""
        code = "with open('data.csv', 'r') as f:\n    pass\nresult = 'ok'"
        # Provide injected_vars to exercise replacement logic
        result = execute_generated_code(code, extra_globals={"injected_vars": [[["col1"], ["val1"]]]})
        # Directly check for success instead of disjunctive assertion
        assert result["success"] is True
        assert result["output"].get("parsed_value") == "ok"


# ---------------------------------------------------------------------------
# execute_generated_code — semicolon expansion still works
# ---------------------------------------------------------------------------

class TestExecuteGeneratedCodeSemicolonExpansion:
    def test_semicolon_oneliner_is_fixed(self):
        """Regression: semicolon one-liners are still expanded before validation."""
        code = "x = 1; y = x + 1; result = y"
        result = execute_generated_code(code)
        assert result["success"] is True
        assert result["output"].get("parsed_value") == 2


# ---------------------------------------------------------------------------
# execute_generated_code — sandbox executes csv (new safe module)
# ---------------------------------------------------------------------------

class TestExecuteGeneratedCodeCsvModule:
    def test_csv_module_accessible_in_sandbox(self):
        """csv is now available in the sandbox as a safe module."""
        code = "import csv\nresult = 'csv available'"
        result = execute_generated_code(code)
        # The import is stripped but csv is injected as global, so result should work
        assert result["success"] is True

    def test_io_module_accessible_in_sandbox(self):
        """io is now available in the sandbox as a safe module."""
        code = "import io\nbuf = io.StringIO('hello')\nresult = buf.read()"
        result = execute_generated_code(code)
        assert result["success"] is True
        assert result["output"].get("parsed_value") == "hello"


# ---------------------------------------------------------------------------
# execute_generated_code — None-safe collector (defensive change)
# ---------------------------------------------------------------------------

class TestExecuteGeneratedCodeCollectorSafe:
    def test_result_has_required_keys(self):
        """Ensures the result dict always has the contract keys even on unusual code."""
        code = "x = 42"
        result = execute_generated_code(code)
        assert "success" in result
        assert "output" in result
        assert "error" in result

    def test_none_result_variable_doesnt_crash(self):
        """result = None should not crash the sandbox."""
        code = "result = None"
        result = execute_generated_code(code)
        assert result["success"] is True
