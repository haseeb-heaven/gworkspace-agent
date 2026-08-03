## 2024-05-24 - [Command Injection]
**Vulnerability:** Use of `shell=os.name == "nt"` in `subprocess.run` with a list of arguments in `framework/task_runner.py`.
**Learning:** Using `shell=True` with a list of arguments on Windows still triggers shell interpretation of metacharacters, leading to potential shell injection vulnerabilities.
**Prevention:** Always use `shell=False` (or omit the argument) when passing a list of arguments to `subprocess` functions, even on Windows.
