## 2024-08-17 - Command Injection Risk in Subprocess
**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` in `framework/task_runner.py` which passes `shell=True` on Windows.
**Learning:** Using `shell=True` (even conditionally based on OS) when passing a command list (like `[sys.executable, "-m", ...]`) is generally unnecessary and creates a potential shell injection vector if any of the array elements were to incorporate unsanitized input. Windows doesn't need `shell=True` to execute `sys.executable`.
**Prevention:** Always use `shell=False` for executing explicit binaries/modules via a command list, unless shell builtins are specifically required.
