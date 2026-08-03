## 2026-05-22 - Subprocess Shell Execution on Windows
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` while passing arguments as a list.
**Learning:** On Windows, passing a list of arguments to a subprocess with `shell=True` still triggers shell interpretation of metacharacters, leading to potential shell injection vulnerabilities.
**Prevention:** Always set `shell=False` when executing scripts or modules with a list of arguments, regardless of the operating system, unless specifically executing a raw shell command string.
