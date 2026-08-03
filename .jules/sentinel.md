## 2024-06-28 - Windows shell=True command injection
**Vulnerability:** subprocess.run used shell=os.name == "nt" (which evaluates to True on Windows).
**Learning:** Even when passing arguments as a list to subprocess on Windows, if shell=True is set, Windows processes shell metacharacters, leading to command injection if input is dynamic.
**Prevention:** Always use shell=False by default (which is the Python default) and pass arguments as lists, even on Windows.
