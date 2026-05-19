## 2024-11-20 - [Command Injection via shell=True on Windows]
**Vulnerability:** Use of `shell=os.name == "nt"` with a list of arguments in `subprocess.run` creates a command injection risk on Windows systems.
**Learning:** Even when arguments are passed as a list, setting `shell=True` on Windows causes `cmd.exe` to parse the arguments and interpret shell metacharacters, potentially leading to arbitrary command execution if an attacker can control any of the arguments.
**Prevention:** Always use `shell=False` (the default) when using `subprocess.run` with a list of arguments, especially when dealing with dynamic input.
