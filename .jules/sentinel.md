## 2023-10-27 - [High] Command Injection via subprocess.run
**Vulnerability:** A command injection vulnerability in `framework/task_runner.py` due to using `shell=os.name == "nt"` with `subprocess.run`.
**Learning:** `shell=True` on Windows with untrusted input can lead to command injection. Since the command is passed as a list of strings, `shell=os.name == "nt"` is unnecessary and introduces a vulnerability. Additionally, removing `shell=True` fixes a bug with the `timeout=60` argument on Windows: with `shell=True`, a timeout would only kill the `cmd.exe` parent process, leaving the `pytest` process running as an orphan.
**Prevention:** Always use `shell=False` unless absolutely necessary and properly quote/escape inputs.
