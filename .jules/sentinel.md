## 2024-10-01 - 🛡️ Sentinel: [HIGH] Fix subprocess call with shell=True
**Vulnerability:** Unnecessary use of `shell=True` conditionally in `subprocess.run` calls.
**Learning:** Developers sometimes add `shell=True` for Windows compatibility out of habit without realizing the command injection risks it introduces, even if the current command parameters are mostly static.
**Prevention:** Avoid `shell=True` unless absolutely necessary (e.g. relying on shell builtins like `dir` or `echo`).
