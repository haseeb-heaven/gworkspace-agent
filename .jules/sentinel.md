## 2024-07-25 - [Command Injection via OS-specific Shell Argument]
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"` when executing a command list.
**Learning:** Developers mistakenly believe Windows requires `shell=True` to execute binaries like `sys.executable`. This creates a command injection vulnerability and triggers Bandit B602 alerts.
**Prevention:** Always explicitly pass `shell=False` for `subprocess.run` when using a command list, regardless of the operating system.
