## 2024-05-24 - Command Injection Risk with Conditional Shell Execution
**Vulnerability:** Subprocess calls conditionally using `shell=True` on Windows (`shell=os.name == "nt"`) without safe input handling.
**Learning:** Using `shell=True` even selectively (like only on Windows) opens the application to Command Injection vulnerabilities. Windows doesn't require `shell=True` to execute binaries like `sys.executable`.
**Prevention:** Always use `shell=False` across all platforms when passing a list of arguments to `subprocess.run()`.
