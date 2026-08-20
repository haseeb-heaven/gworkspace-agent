## 2024-05-18 - Fix command injection vulnerability in task runner
**Vulnerability:** Found `subprocess.run` with `shell=os.name == "nt"` in `framework/task_runner.py`
**Learning:** `shell=True` (which evaluating `os.name == "nt"` is on Windows) on `subprocess.run` can lead to command injection if arguments are unsanitized. Specifically, executing Python scripts or binaries on Windows does not actually require `shell=True`, and using it poses an unnecessary risk.
**Prevention:** Always use `shell=False` across all platforms unless there's a strict, necessary requirement to run shell built-ins or use pipes. For executing Python modules (like `sys.executable -m pytest`), `shell=False` is entirely sufficient and safer.
