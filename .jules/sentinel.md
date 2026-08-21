## 2026-08-21 - Command Injection Risk with shell=True on Windows
**Vulnerability:** Invoking `subprocess.run` with `shell=os.name == "nt"` evaluates to `shell=True` on Windows environments, which introduces a Command Injection vulnerability (CWE-78) when executing commands, resulting in a Bandit B602 warning.
**Learning:** The conditional was likely added under the false assumption that Windows strictly requires `shell=True` to execute binaries or scripts with `subprocess`. However, Windows can safely execute list-format commands (like `sys.executable` with arguments) using `shell=False`.
**Prevention:** Always explicitly pass `shell=False` to `subprocess.run()` across all platforms to prevent Command Injection vulnerabilities.
