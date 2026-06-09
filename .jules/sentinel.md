## 2025-02-27 - Subprocess Shell Injection Vulnerability in Task Runner
**Vulnerability:** Found `subprocess.run` called with `shell=os.name == "nt"` in `framework/task_runner.py` (Bandit B602).
**Learning:** Using `shell=True` on Windows with lists of arguments is dangerous as Windows shell interprets the arguments, allowing metacharacters like `&` or `|` in variables like `marker_expr` to inject arbitrary commands.
**Prevention:** Always use `shell=False` (default) when using `subprocess.run` with a list of arguments, even on Windows, unless explicitly needing a shell built-in like `dir` or `echo`.
