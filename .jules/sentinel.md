## 2026-06-30 - Fix shell injection risk on Windows in task runner
**Vulnerability:** `subprocess.run` was called with `shell=os.name == "nt"`, evaluating to `shell=True` on Windows environments while passing a list of arguments.
**Learning:** Using `shell=True` with an argument list on Windows can still trigger the command interpreter (`cmd.exe`) and expose the application to shell injection if variables (like `marker_expr`) contain metacharacters.
**Prevention:** Explicitly use `shell=False` when executing commands with a list of arguments unless shell features (like pipes or redirects) are strictly required. Python handles execution natively on Windows without needing a shell interpreter.
