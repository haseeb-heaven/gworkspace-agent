## 2024-05-24 - [subprocess.run Command Injection Risk]
**Vulnerability:** subprocess call with shell=True on Windows identified, command injection vulnerability (Bandit B602).
**Learning:** Using `shell=os.name == "nt"` introduces a severe command injection vulnerability on Windows systems. Windows does not strictly require `shell=True` to execute binaries like `sys.executable`.
**Prevention:** Always explicitly pass `shell=False` when invoking `subprocess.run` with a command list across all platforms to prevent command injection vulnerabilities.
