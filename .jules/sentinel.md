## 2023-10-27 - [High] Command Injection via subprocess.run
**Vulnerability:** A command injection vulnerability in `framework/task_runner.py` due to using `shell=os.name == "nt"` with `subprocess.run`.
**Learning:** `shell=True` on Windows with untrusted input can lead to command injection. Since the command is passed as a list of strings, `shell=os.name == "nt"` is unnecessary and introduces a vulnerability. Additionally, removing `shell=True` fixes a bug with the `timeout=60` argument on Windows: with `shell=True`, a timeout would only kill the `cmd.exe` parent process, leaving the `pytest` process running as an orphan.
**Prevention:** Always use `shell=False` unless absolutely necessary and properly quote/escape inputs.

## 2023-10-27 - [High] Path Traversal and Information Disclosure in Gradio App
**Vulnerability:** CodeQL detected a path traversal vulnerability in `gradio_app.py` when opening `file_path`, and an information disclosure vulnerability where sensitive client config structures were printed using `print()`.
**Learning:** Always validate user-provided file paths thoroughly against null bytes, `..`, and absolute path expectations, even when relying on framework constraints like Gradio's temp directories. Furthermore, never log sensitive credential structures even during debugging.
**Prevention:** Implement strict path validations like `\x00 in path`, `.. in path`, and `os.path.isabs(path)`. Ensure logging and print statements do not expose config contents.
