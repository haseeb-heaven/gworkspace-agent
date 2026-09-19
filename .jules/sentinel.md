## 2025-02-27 - [Fix Command Injection in Subprocess]
**Vulnerability:** Found `subprocess.run` called with `shell=os.name == "nt"`.
**Learning:** `shell=True` (even conditionally based on `os.name`) exposes the application to Command Injection vulnerabilities. In Windows, it's not strictly required for binary execution like `sys.executable`.
**Prevention:** Explicitly pass `shell=False` across all platforms (including Windows) when executing command lists via `subprocess.run` or similar subprocess APIs.
