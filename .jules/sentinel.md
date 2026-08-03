## 2025-02-14 - Removed conditional shell=True in subprocess
**Vulnerability:** task_runner.py used `shell=os.name == "nt"` which evaluated to True on Windows, causing a B602 command injection risk.
**Learning:** Even with structured list commands (`cmd`), using `shell=True` on any platform opens the application up to potential command injection. Windows does not strictly require `shell=True` to execute Python modules.
**Prevention:** Always default to `shell=False` for all platforms when calling `subprocess.run`, especially when user input could influence the command components.
