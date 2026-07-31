## 2026-07-26 - Fix Command Injection risk (Bandit B602) in task runner
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` in `framework/task_runner.py` while passing an argument list.
**Learning:** This is a Command Injection risk on Windows because `shell=True` causes the argument list to be converted to a string and executed in `cmd.exe`.
**Prevention:** Always use `shell=False` across all platforms (including Windows) when executing binaries directly (e.g. `sys.executable`). Windows does not strictly require `shell=True` to execute binaries.
