## 2026-06-08 - Fixed Command Injection risk in subprocess.run
**Vulnerability:** Used `shell=os.name == "nt"` with a list-based command (`cmd = [sys.executable, ...]`) inside `subprocess.run()`.
**Learning:** Even though the command was passed as a list, setting `shell=True` on Windows triggers the system shell (`cmd.exe`), which parses arguments and interprets special characters differently, opening up a Command Injection vector.
**Prevention:** Always use `shell=False` (the default) when executing scripts or modules via `subprocess`, regardless of the underlying OS, unless strictly running a shell-native built-in command and safely escaping strings.
