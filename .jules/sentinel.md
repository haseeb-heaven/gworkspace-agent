## 2024-07-24 - [CRITICAL] Command Injection Vulnerability in Task Runner

**Vulnerability:** subprocess.run is called with `shell=os.name == "nt"` which opens up command injection vulnerabilities on Windows.
**Learning:** `shell=True` was likely added as a convenience/assumption for Windows compatibility but is rarely actually required when passing lists of arguments.
**Prevention:** Always use `shell=False` for all platforms unless strictly required to invoke shell-specific features (and in those cases use extreme caution with user input).
