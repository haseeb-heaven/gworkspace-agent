## 2026-10-01 - Fix command injection vulnerability in task_runner
**Vulnerability:** Found `subprocess.run` with `shell=os.name == "nt"` in `framework/task_runner.py` which can lead to command injection on Windows systems.
**Learning:** Using `shell=True` (or dynamically enabling it based on OS) when passing untrusted variables in a command list exposes the system to command injection risks.
**Prevention:** Always use `shell=False` when passing arguments as a list. The executable path is already provided safely in the `cmd` list argument, so shell execution is not needed and poses a significant security risk.
