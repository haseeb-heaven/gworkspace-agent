## 2024-06-26 - [High] subprocess call with shell=True identified
**Vulnerability:** Found `subprocess.run(..., shell=os.name == "nt")` with uncontrolled arguments in `framework/task_runner.py`.
**Learning:** `shell=True` on Windows allows attackers to execute arbitrary shell commands if variables within the command string are not properly sanitized.
**Prevention:** Avoid `shell=True` wherever possible. If it's used with `os.name == "nt"`, only do so if absolutely necessary and strictly sanitize inputs. The current script doesn't execute user inputs directly via this vector in a way that requires `shell=True`, so it can be safely removed or passed as `shell=False`.
