## 2026-05-17 - [Subprocess Shell Injection on Windows]
**Vulnerability:** `subprocess.run` called with `shell=os.name == 'nt'` and a list of arguments.
**Learning:** On Windows, using `shell=True` with a list of arguments still triggers shell interpretation of metacharacters, potentially leading to shell injection.
**Prevention:** Avoid using `shell=True` in `subprocess` calls when executing scripts or modules. Pass a list of arguments and set `shell=False` (default).
