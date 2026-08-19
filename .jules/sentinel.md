## 2024-05-18 - Prevent Command Injection in subprocess calls
**Vulnerability:** Use of `shell=os.name == "nt"` in `subprocess.run` with a command list.
**Learning:** `shell=True` on Windows with a list of arguments allows potential command injection. Bandit flags this (B602). With a command list, Windows does not require `shell=True` to execute binaries like `sys.executable`.
**Prevention:** Always use `shell=False` across all platforms when passing a command list to `subprocess.run` to prevent command injection vulnerabilities.
