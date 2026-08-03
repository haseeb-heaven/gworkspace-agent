## 2025-05-31 - Fix shell=True vulnerability in subprocess
**Vulnerability:** subprocess.run was called with shell=True when evaluating on Windows. Passing arguments as a list with shell=True triggers cmd.exe execution of arguments, allowing shell injection on Windows.
**Learning:** Even when passing args as a list instead of a string, shell=True on Windows passes them to cmd.exe, opening up injection risks.
**Prevention:** Avoid shell=True in subprocess unless strictly executing shell built-ins. Pass arguments as a list and use shell=False.
