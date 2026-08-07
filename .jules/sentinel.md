## 2026-08-07 - Avoid shell=True for sys.executable in subprocess
**Vulnerability:** Subprocess command execution with shell=True when passing a list of arguments for `sys.executable`. (Bandit B602)
**Learning:** The code used `shell=os.name == "nt"` which unnecessarily activated the shell on Windows. Windows does not strictly require `shell=True` to execute binaries like `sys.executable`. Passing a list of arguments with `shell=True` is dangerous and flagged as a HIGH risk for Command Injection.
**Prevention:** Explicitly pass `shell=False` across all platforms (including Windows) when invoking `subprocess.run` with a command list to prevent Command Injection vulnerabilities and avoid Bandit B602 alerts.
