## 2024-08-16 - Subprocess Command Injection on Windows
**Vulnerability:** Found `shell=os.name == "nt"` being used in `subprocess.run(cmd, ...)` in `framework/task_runner.py`.
**Learning:** Using `shell=True` (even conditionally on Windows) when passing a list of arguments is a command injection risk and flagged by Bandit (B602). Windows does not require `shell=True` to execute binaries like `sys.executable`.
**Prevention:** Always use `shell=False` when calling `subprocess.run` with a command list, across all platforms.
