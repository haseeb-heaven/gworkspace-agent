## 2025-02-14 - Fix subprocess shell=True vulnerability
**Vulnerability:** subprocess.run uses shell=os.name == "nt" which can lead to command injection.
**Learning:** Windows does not strictly require shell=True to execute binaries like sys.executable. Using shell=True with a command list can cause command injection vulnerabilities and triggers Bandit B602 alerts.
**Prevention:** Explicitly pass shell=False across all platforms when invoking subprocess.run with a command list.
