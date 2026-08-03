## 2024-05-29 - [HIGH] Fix shell injection vulnerability in task_runner
**Vulnerability:** subprocess.run was called with `shell=os.name == "nt"`, allowing potential shell injection on Windows.
**Learning:** Even if `cmd` is passed as a list, setting `shell=True` on Windows can still interpret metacharacters, leading to shell injection risks.
**Prevention:** Always explicitly set `shell=False` (or let it default to False) when passing a list of arguments to subprocess functions.
