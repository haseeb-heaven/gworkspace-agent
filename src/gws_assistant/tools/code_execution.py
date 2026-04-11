"""Code execution tool for the LangChain agent."""

import io
import contextlib
import subprocess
import sys
import json
import base64
from typing import Any
from RestrictedPython import compile_restricted, safe_globals, safe_builtins, utility_builtins
from RestrictedPython.PrintCollector import PrintCollector

from langchain_core.tools import tool
from gws_assistant.models import CodeExecutionResult

@tool
def code_execution_tool(code: str) -> dict[str, Any]:
    """
    Executes Python 3 code in a restricted, sandboxed environment.
    Use this to perform complex mathematical processing, formatting text, or logical steps that require actual code execution.
    Features:
    - Supported builtins: basic math, string manipulation, dicts, lists.
    - Unsupported: File I/O, networking, imports.
    - Max execution time: 10 seconds.
    - Captures STDOUT and returns it.
    
    Args:
        code: The Python 3 code to execute.
        
    Returns:
        JSON compatible dict with STDOUT, success status and error messages.
    """
    # Encapsulated script to run in a separate process for maximum isolation and reliability on Windows
    # We use base64 encoding for the user code to avoid shell escaping issues
    code_b64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')
    
    bootstrap_script = f"""
import sys
import io
import contextlib
import json
import base64
from RestrictedPython import compile_restricted, safe_globals, safe_builtins, utility_builtins
from RestrictedPython.PrintCollector import PrintCollector

def get_safe_globals():
    safe_g = safe_globals.copy()
    safe_g["__builtins__"] = safe_builtins.copy()
    safe_g["__builtins__"].update(utility_builtins)
    safe_g["_print_"] = PrintCollector
    safe_g["_getattr_"] = getattr
    safe_g["_setattr_"] = setattr
    safe_g["_getiter_"] = iter
    safe_g["_getitem_"] = lambda obj, key: obj[key]
    safe_g["_write_"] = lambda obj: obj
    return safe_g

def run():
    code_base64 = "{code_b64}"
    code = base64.b64decode(code_base64).decode('utf-8')
    
    result = {{"stdout": "", "stderr": "", "success": False, "error": None}}
    try:
        byte_code = compile_restricted(code, filename="<string>", mode="exec")
        sandbox_globals = get_safe_globals()
        
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            exec(byte_code, sandbox_globals)

        if "_print" in sandbox_globals:
             result["stdout"] = str(sandbox_globals["_print"]())
             
        buffer_val = output_buffer.getvalue()
        if buffer_val:
             if result["stdout"]:
                  result["stdout"] += "\\n" + buffer_val
             else:
                  result["stdout"] = buffer_val
             
        result["success"] = True
    except Exception as e:
        result["success"] = False
        result["error"] = f"{{type(e).__name__}}: {{str(e)}}"
    
    sys.stdout = sys.__stdout__ # Reset stdout to print the JSON result
    print(json.dumps(result))

if __name__ == "__main__":
    run()
"""
    
    try:
        proc = subprocess.run(
            [sys.executable, "-c", bootstrap_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if proc.returncode != 0:
             return {
                 "code": code,
                 "stdout": proc.stdout,
                 "stderr": proc.stderr,
                 "success": False,
                 "error": f"Process exited with code {proc.returncode}"
             }
             
        # Extract the JSON payload from the last line of output
        lines = proc.stdout.strip().splitlines()
        if not lines:
             return {
                 "code": code,
                 "stdout": "",
                 "stderr": proc.stderr,
                 "success": False,
                 "error": "No output from sandbox process"
             }
             
        try:
             payload = json.loads(lines[-1])
             return {
                 "code": code,
                 "stdout": payload.get("stdout", ""),
                 "stderr": proc.stderr,
                 "success": payload.get("success", False),
                 "error": payload.get("error")
             }
        except json.JSONDecodeError:
             return {
                 "code": code,
                 "stdout": proc.stdout,
                 "stderr": proc.stderr,
                 "success": False,
                 "error": "Failed to parse sandbox output as JSON"
             }

    except subprocess.TimeoutExpired:
        return {
            "code": code,
            "stdout": "",
            "stderr": "",
            "success": False,
            "error": "TimeoutError: Execution exceeded 10 seconds limit."
        }
    except Exception as e:
        return {
            "code": code,
            "stdout": "",
            "stderr": "",
            "success": False,
            "error": f"InternalError: {str(e)}"
        }
