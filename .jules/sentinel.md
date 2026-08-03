## 2024-07-08 - [subprocess shell=True vulnerability on Windows]
**Vulnerability:** Found `shell=os.name == "nt"` in `subprocess.run` inside `framework/task_runner.py`, effectively resolving to `shell=True` on Windows.
**Learning:** Developers sometimes use `shell=True` on Windows to resolve pathing or executable extensions seamlessly, but it unnecessarily increases the risk of command injection.
**Prevention:** Always use `shell=False` for cross-platform compatibility and ensure paths are passed correctly in the command list, even on Windows.
