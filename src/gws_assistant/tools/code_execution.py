"""Code execution tool for the LangChain agent."""

import io
import contextlib
from typing import Any
from RestrictedPython import compile_restricted, safe_globals, safe_builtins, utility_builtins
from RestrictedPython.PrintCollector import PrintCollector

from langchain_core.tools import tool
from gws_assistant.models import CodeExecutionResult
import multiprocessing
import queue

# Restricted Python safe environmnt
def get_safe_globals() -> dict[str, Any]:
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

def _run_in_sandbox(code: str, return_queue: multiprocessing.Queue):
    """Executes the code securely and posts results to a queue."""
    result = CodeExecutionResult(code=code)
    try:
        # Compile source code with RestrictedPython
        byte_code = compile_restricted(
            code,
            filename="<string>",
            mode="exec"
        )
        sandbox_globals = get_safe_globals()
        
        # Capture standard output correctly via restricted python mechanism
        # Using contextlib redirect_stdout helps catch any print calls not caught by RestrictedPython 
        # (Though with _print_ mechanism it is typically caught in printed).
        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            exec(byte_code, sandbox_globals)

        # Get `_print()` output from PrintCollector 
        if "_print" in sandbox_globals:
             result.stdout = sandbox_globals["_print"]()
             
        # Add normal stdout buffer to it
        buffer_val = output_buffer.getvalue()
        if buffer_val:
             if result.stdout:
                  result.stdout += "\n" + buffer_val
             else:
                  result.stdout = buffer_val
             
             
        result.success = True
        
    except Exception as e:
        result.success = False
        result.error = f"{type(e).__name__}: {str(e)}"
        
    return_queue.put(result)


@tool
def code_execution_tool(code: str) -> dict[str, Any]:
    """
    Executes Python 3 code in a restricted, sandboxed environment.
    Use this to perform complex mathematical processing, formatting text, or logical steps that require actual code execution.
    Features:
    - Supported builtins: basic math, string manipulation, dicts, lists.
    - Unsupported: File I/O, networking, imports (`os`, `sys`, `socket` etc. are heavily restricted).
    - Max execution time: 5 seconds.
    - Captures STDOUT and returns it.
    
    Args:
        code: The Python 3 code to execute.
        
    Returns:
        JSON compatible dict with STDOUT, success status and error messages.
    """
    queue_res = multiprocessing.Queue()
    process = multiprocessing.Process(target=_run_in_sandbox, args=(code, queue_res))
    process.start()
    
    # Wait for completion or timeout
    process.join(timeout=5)
    
    result = CodeExecutionResult(code=code)
    
    if process.is_alive():
        # Timeout occurred -> terminate the process forcefully
        process.terminate()
        process.join()  # wait for it to actually terminate
        result.success = False
        result.error = "TimeoutError: Execution exceeded 5 seconds limit."
    else:
        try:
            # Process ended gracefully, retrieve the result
            result = queue_res.get(block=False)
        except queue.Empty:
            result.success = False
            result.error = "ProcessError: Sandbox process crashed unexpectedly without returning results."
            
    # Serialize to dictionary for LangChain agent compatibility
    return {
        "code": result.code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.success,
        "error": result.error
    }
