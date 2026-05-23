## 2024-05-23 - Prevent Command Injection via Subprocess
**Vulnerability:** Found `subprocess.run` called with `shell=os.name == "nt"` and a list of arguments in `framework/task_runner.py`.
**Learning:** Even when passing a list to `subprocess.run`, setting `shell=True` on Windows triggers shell interpretation of metacharacters, leading to command injection risks.
**Prevention:** Always use `shell=False` (the default) when executing scripts or modules with a list of arguments, regardless of the operating system.
