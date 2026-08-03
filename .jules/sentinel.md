## 2026-06-13 - [CRITICAL] Shell injection risk with os.name == 'nt'
**Vulnerability:** subprocess.run was called with shell=os.name == 'nt', which creates a shell injection vector on Windows, even if passing a list of arguments.
**Learning:** In python subprocess, passing shell=True on Windows attempts shell parsing on the list, causing shell character expansion, whereas on Linux lists are safe.
**Prevention:** Strictly enforce shell=False for all list-based command construction unless invoking a shell built-in.
