## 2025-02-14 - Fix subprocess.run shell injection vulnerability
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` in `framework/task_runner.py`.
**Learning:** Using `shell=True` with a list of arguments on Windows can lead to shell injection vulnerabilities, as the list might be interpreted by the shell in unsafe ways. Even when it is conditional (`os.name == "nt"`), it exposes Windows users to risks.
**Prevention:** Always use `shell=False` when calling `subprocess.run` with a list of arguments, regardless of the operating system, to ensure arguments are passed safely without shell interpretation.
