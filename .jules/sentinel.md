## 2024-10-24 - Fix subprocess shell=True vulnerability
**Vulnerability:** subprocess.run was called with shell=os.name == "nt" for a list of arguments.
**Learning:** Windows does not strictly require shell=True to execute binaries like sys.executable. Passing shell=True with an argument list can lead to command injection if elements aren't properly escaped.
**Prevention:** Always use shell=False across all platforms when passing a list of arguments to subprocess.run.
