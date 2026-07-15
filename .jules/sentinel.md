## 2026-07-15 - [CRITICAL] Prevent Command Injection in Task Runner

**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` in `framework/task_runner.py` which sets `shell=True` on Windows environments, creating a potential command injection vector.
**Learning:** Evaluated boolean statements (like `os.name == "nt"`) are sometimes incorrectly used by developers to conditionally apply `shell=True` on Windows. However, when executing a direct binary using an argument list (like `sys.executable`), Windows does not strictly require `shell=True`.
**Prevention:** Always use `shell=False` across all platforms when passing a list of arguments to `subprocess.run`, especially when the first argument is a direct path to an executable like `sys.executable`.
