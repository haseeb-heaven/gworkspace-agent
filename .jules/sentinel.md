## 2024-10-03 - [HIGH] Fix command injection risk in task_runner
**Vulnerability:** subprocess call with `shell=os.name == "nt"` identified, which executes the shell on Windows, leading to potential command injection.
**Learning:** Using `shell=True` (or equivalent like `shell=os.name == "nt"`) is highly insecure as it passes execution to the shell, making command injection possible.
**Prevention:** Avoid `shell=True` when passing a list of arguments unless explicitly needed for built-in shell commands.
