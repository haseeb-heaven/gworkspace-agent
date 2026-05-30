## 2026-05-30 - Subprocess shell=True Vulnerability
**Vulnerability:** Found a high severity shell injection vulnerability (`B602`) in `framework/task_runner.py` where `subprocess.run` was called with `shell=os.name == "nt"`.
**Learning:** This existed because `shell=True` with a list of arguments does not behave the same way on Windows as on Unix. On Windows, it allows meta-characters to be interpreted unsafely, leading to command injection even when the command arguments are passed as a list.
**Prevention:** Avoid `shell=True` completely. When running scripts or commands, pass arguments as a list and use the default `shell=False`.
