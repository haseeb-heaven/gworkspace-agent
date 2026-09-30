## 2024-05-15 - [Remove shell=True in subprocess.run]
**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` with a list `cmd` argument in `framework/task_runner.py`.
**Learning:** `shell=True` with `subprocess.run()` is a security risk, allowing for potential command injection. It is also unnecessary when the `cmd` argument is passed as a list of strings (as it is in this case, `[sys.executable, "-m", "pytest", "-v", "-m", marker_expr]`).
**Prevention:** Avoid `shell=True` unless absolutely necessary (e.g. running complex shell pipelines), and even then, make sure to sanitize arguments. When calling an executable with arguments, pass them as a list to `subprocess.run()` without `shell=True`.
