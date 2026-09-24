## 2024-05-01 - Avoid shell=True in subprocess on Windows
**Vulnerability:** The codebase conditionally sets `shell=True` on Windows when invoking `subprocess.run()` with a command list (e.g., `sys.executable`). This introduces a command injection vulnerability (Bandit B602).
**Learning:** Windows does not strictly require `shell=True` to execute binaries like `sys.executable` when arguments are passed as a list. Using `shell=True` is an anti-pattern when it is not explicitly needed.
**Prevention:** Always explicitly pass `shell=False` in `subprocess.run` calls when a command list is used, across all platforms.
