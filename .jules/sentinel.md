## 2026-05-27 - Shell Injection Risk via shell=True in Windows compatibility check
**Vulnerability:** Found `shell=os.name == "nt"` in a `subprocess.run` call inside `framework/task_runner.py`, which evaluates to `shell=True` on Windows environments.
**Learning:** This existed because the original author may have incorrectly believed Windows required a shell to execute `python.exe` or a Python script as a list of arguments, but this creates a command injection risk when passing a list to `subprocess.run` with `shell=True`.
**Prevention:** Always use `shell=False` (the default) when executing scripts or executables with `subprocess.run` and pass arguments as a list to avoid OS shell metacharacter injection vulnerabilities, regardless of the operating system.
