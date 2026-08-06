## 2024-05-27 - [Fix OS Command Injection via shell=True in subprocess.run]
**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` in `framework/task_runner.py` which allows command injection on Windows platforms.
**Learning:** `shell=True` (or expressions that evaluate to it) with unsanitized/command list inputs opens up OS command injection vulnerabilities. `subprocess.run` accepts a list and doesn't strictly need `shell=True` to execute commands securely, even on Windows.
**Prevention:** Explicitly pass `shell=False` across all platforms (including Windows) to prevent Command Injection vulnerabilities and avoid Bandit B602 alerts.
