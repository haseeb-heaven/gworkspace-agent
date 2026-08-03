## 2026-05-21 - [CRITICAL] Fix Command Injection Vulnerability in Task Runner
**Vulnerability:** Use of `shell=os.name == "nt"` inside `subprocess.run` with a list of arguments in `framework/task_runner.py`.
**Learning:** On Windows, `shell=True` with a list still triggers shell interpretation of metacharacters, leading to command injection vulnerabilities if an argument contains shell variables or separators.
**Prevention:** Avoid using `shell=True` in `subprocess` calls. Always set `shell=False` (or rely on the default) when executing scripts or modules with a list of arguments.
