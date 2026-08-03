## 2026-05-24 - Avoid shell=True in Windows Subprocess
**Vulnerability:** High severity command injection risk discovered in `framework/task_runner.py` where `subprocess.run()` was using `shell=os.name == "nt"` with a list of arguments.
**Learning:** On Windows, using `shell=True` with a list argument still triggers shell interpretation of metacharacters, unlike POSIX systems. If any element of the list (like `self.service`) is untrusted, it can lead to command injection.
**Prevention:** Always use `shell=False` (the default) when passing a list of arguments to `subprocess`, and avoid `shell=True` entirely unless explicitly necessary with a single string command and sanitized inputs.
