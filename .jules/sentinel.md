## 2024-05-24 - [B602] subprocess with shell=True
**Vulnerability:** subprocess call with shell=os.name == "nt" when args is a sequence.
**Learning:** On Windows, shell=True with a sequence argument can be unsafe because it triggers the shell interpreter and handles characters differently, overriding the normal safe behavior. Avoid `shell=True` or dynamic assignments based on OS name if passing sequence arguments.
**Prevention:** Use `shell=False` default when passing a sequence of arguments to `subprocess.run()`.
