## 2024-07-02 - [shell=True on Windows]
**Vulnerability:** Found `subprocess.run` with `shell=os.name == "nt"` and an argument list in `framework/task_runner.py`.
**Learning:** Using `shell=True` on Windows with list arguments doesn't escape safely, creating a command injection vulnerability. Since `sys.executable` (a direct binary) is used as the command, `shell=False` is strictly correct and safer across platforms.
**Prevention:** Avoid `shell=True` unless explicitly calling built-in shell commands (like `dir`), and even then, heavily sanitize all interpolated inputs. Always default to `shell=False` for executing python scripts or standard binaries.
