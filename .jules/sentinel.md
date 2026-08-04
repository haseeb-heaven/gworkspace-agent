
## 2024-05-24 - Command Injection Risk in Cross-Platform Shell Execution
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` which evaluates to `True` on Windows, exposing a command injection vulnerability (Bandit B602).
**Learning:** Windows does not strictly require `shell=True` to execute commands passed as a list (like `sys.executable`). Setting it to `True` unnecessarily opens up shell injection risks if argument inputs aren't perfectly sanitized.
**Prevention:** Always explicitly pass `shell=False` to `subprocess` functions when passing command lists, regardless of the operating system (Windows/Linux/macOS), unless specifically executing built-in shell commands.
