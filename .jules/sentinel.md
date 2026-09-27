## 2026-09-27 - Command Injection risk with shell=os.name == "nt"
**Vulnerability:** Invoking `subprocess.run(..., shell=os.name == "nt")` for command lists on Windows.
**Learning:** Even though developers sometimes think `shell=True` is needed on Windows for executing binaries or Python modules, passing a list to `subprocess.run` with `shell=True` introduces command injection risks, as arguments might not be properly quoted/escaped by the shell. `sys.executable` works perfectly without `shell=True`.
**Prevention:** Always enforce `shell=False` for `subprocess` calls executing command lists across all platforms to avoid Bandit B602 alerts and prevent command injection.
