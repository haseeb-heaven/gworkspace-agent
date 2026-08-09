## 2024-05-18 - [Fix Command Injection in Task Runner]
**Vulnerability:** Command injection vulnerability in `subprocess.run` due to conditional `shell=True` on Windows (`shell=os.name == "nt"`).
**Learning:** Hardcoding `shell=True` on Windows under the assumption that it is required for all `subprocess` execution is flawed. When invoking binary executables (like `sys.executable`), `shell=False` works perfectly fine and is required to avoid execution of shell metacharacters embedded in user input.
**Prevention:** Always explicitly set `shell=False` across all operating systems when constructing explicit command arrays (`subprocess.run(["cmd", "arg"])`), especially when dynamic strings are appended to the array.
