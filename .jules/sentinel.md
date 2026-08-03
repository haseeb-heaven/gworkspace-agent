## 2024-05-24 - [Subprocess Shell Injection on Windows]
**Vulnerability:** Found `subprocess.run` called with `shell=os.name == "nt"` and a list of arguments in `framework/task_runner.py`.
**Learning:** On Windows, using `shell=True` with a list of arguments causes `subprocess` to join them into a string and execute via `cmd.exe /c`. This exposes the application to shell injection if any arguments contain shell metacharacters (like `&` or `|`), negating the security benefit of passing arguments as a list.
**Prevention:** Always use `shell=False` (the default) when passing arguments as a list to `subprocess.run()`, even on Windows, unless explicitly executing a built-in shell command or `.bat` file.
