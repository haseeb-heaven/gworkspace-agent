## 2024-05-18 - Fix Command Injection Vulnerability in subprocess.run
**Vulnerability:** subprocess call with shell=True identified in framework/task_runner.py.
**Learning:** Using `shell=os.name == "nt"` with `subprocess.run` on Windows opens the code to Command Injection. Windows does not strictly require `shell=True` to execute binaries like `sys.executable`.
**Prevention:** Explicitly pass `shell=False` to `subprocess.run` across all platforms (including Windows) to prevent Command Injection vulnerabilities.
