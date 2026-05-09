
import pytest
from gws_assistant.tools.code_execution import execute_generated_code

def test_execute_with_open_replacement_multi_line():
    code = """
with open("test.txt") as f:
    # This should be replaced by f = injected_vars[0] ...
    # and this body should be dedented (if it were orphaned)
    # but with AST it should just work.
    result = "success"
"""
    # We need to provide injected_vars in extra_globals
    extra_globals = {"injected_vars": ["mock_file_content"]}
    
    res = execute_generated_code(code, extra_globals=extra_globals)
    
    assert res["success"], f"Execution failed: {res['error']}"
    assert res["output"]["parsed_value"]["result"] == "success"

def test_execute_with_open_one_liner():
    code = 'with open("test.txt") as f: result = "one-liner"'
    extra_globals = {"injected_vars": ["mock_file_content"]}
    
    res = execute_generated_code(code, extra_globals=extra_globals)
    
    assert res["success"], f"Execution failed: {res['error']}"
    assert res["output"]["parsed_value"]["result"] == "one-liner"

def test_execute_with_open_and_return_removal():
    code = """
with open("test.txt") as f:
    result = "return-removed"
    return result
"""
    extra_globals = {"injected_vars": ["mock_file_content"]}
    
    res = execute_generated_code(code, extra_globals=extra_globals)
    
    assert res["success"], f"Execution failed: {res['error']}"
    assert res["output"]["parsed_value"]["result"] == "return-removed"

def test_execute_with_open_fallback_on_invalid_syntax():
    # If the code has a syntax error that makes AST fail, it should fallback to regex
    # and then fail later during validation or execution.
    code = """
with open("test.txt") as f:
    result = "fail"
    if True: # missing pass or something
"""
    # This code is invalid anyway.
    res = execute_generated_code(code)
    assert not res["success"]
    assert "SyntaxError" in res["error"]
