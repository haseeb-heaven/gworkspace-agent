## 2024-05-18 - Remove shell=True in subprocess calls
**Vulnerability:** Found `subprocess.run` called with `shell=True` dynamically set based on the operating system (`shell=os.name == "nt"`) in `framework/task_runner.py`.
**Learning:** Using `shell=True` can lead to command injection if the input is untrusted, and `sys.executable` and `pytest` running on Windows do not require `shell=True`.
**Prevention:** Always use `shell=False` everywhere (including Windows) unless absolutely necessary for specific shell built-ins.
