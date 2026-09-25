## 2024-05-24 - Fix Command Injection Risk in task_runner.py
**Vulnerability:** The `subprocess.run` call in `framework/task_runner.py` uses `shell=os.name == "nt"`.
**Learning:** Using `shell=True` on Windows (which `os.name == "nt"` enables) is not necessary for running Python commands (like `sys.executable -m pytest`) when passing a list, and it introduces a Command Injection vulnerability risk that Bandit B602 warns about. Windows can execute `.exe` binaries without `shell=True`.
**Prevention:** Always use `shell=False` explicitly for all `subprocess.run` calls unless absolutely necessary (e.g. built-in shell commands like `dir` or `echo`), to satisfy Bandit rules and prevent command injection.
