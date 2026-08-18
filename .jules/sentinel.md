## 2025-02-24 - Remove shell=os.name == "nt" from subprocess.run
**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` in `framework/task_runner.py`, which evaluates to `shell=True` on Windows.
**Learning:** `shell=True` is not strictly required on Windows to run executables like `sys.executable` or `pytest`. It introduces a Command Injection vulnerability (Bandit B602 alert) if arguments are not properly sanitized.
**Prevention:** Always use `shell=False` across all platforms for `subprocess.run` with list arguments to prevent Command Injection, ensuring security without sacrificing functionality.
