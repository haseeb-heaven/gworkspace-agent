## 2026-05-16 - [CRITICAL] Command Injection Risk with shell=True on Windows
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` and a list of arguments in `framework/task_runner.py`.
**Learning:** Even when passing arguments as a list to `subprocess.run`, setting `shell=True` on Windows triggers shell interpretation of metacharacters, opening the door to command injection if any argument contains untrusted data.
**Prevention:** Always use `shell=False` (which is the default) in `subprocess.run`, `subprocess.Popen`, etc. when passing arguments as a list, regardless of the operating system. If you must use `shell=True` (which should be avoided if possible), pass the command as a single formatted string and use `shlex.quote` or similar sanitization.
