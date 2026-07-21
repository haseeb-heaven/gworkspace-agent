## 2025-02-27 - [Fix subprocess command injection risk on Windows]
**Vulnerability:** Found `subprocess.run` with `shell=os.name == "nt"` in `framework/task_runner.py`.
**Learning:** `subprocess.run` with a command list (e.g., executing Python modules or scripts) does not strictly require `shell=True` on Windows when invoking `sys.executable`. Passing `shell=True` introduces a command injection vulnerability (and triggers Bandit B602 alerts).
**Prevention:** Always explicitly pass `shell=False` to `subprocess.run` when passing a list of arguments, across all platforms.
