## 2024-05-20 - [Command Injection via shell=True]
**Vulnerability:** subprocess.run was called with shell=True on Windows in framework/task_runner.py, introducing a command injection risk.
**Learning:** Using shell=True enables shell features but allows an attacker to execute arbitrary commands if inputs are not sanitized.
**Prevention:** Always hardcode shell=False across all platforms unless absolutely necessary.
