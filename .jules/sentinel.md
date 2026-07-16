## 2025-02-20 - [HIGH] Fix Command Injection Vulnerability in Subprocess
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` in `framework/task_runner.py`.
**Learning:** Hardcoding `shell=True` on Windows environments for running subprocesses with array arguments creates a severe command injection vulnerability if any of the arguments are user-controlled. The assumption that Windows requires `shell=True` to execute basic python modules using `sys.executable` is incorrect.
**Prevention:** Always explicitly pass `shell=False` to subprocess module calls across all platforms, especially when passing the command as a list array. Do not rely on OS checks to conditionally enable shell execution unless strictly required and thoroughly sanitized.
