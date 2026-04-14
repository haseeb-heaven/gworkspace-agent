# Failure Analysis and Auto-Fixing Workflow

## 1. Input Parsing
- Use regex to extract all `python gws_cli.py --task "..."` commands.
- Sort them by order of appearance.
- Deduplicate if necessary, but preserve sequence.

## 2. Failure Analyzer
When a command fails:
- **Read Stderr:** Look for "Traceback" and the last line of the error.
- **Trace Backwards:** Start from the last line of the traceback and identify the first "project file" (not library file) in the stack.
- **Inspect Context:** Use `read_file` with context around the failing line.
- **Identify Symptom:**
    - `FileNotFoundError`: Check if the file path is correct or if it was supposed to be created by a previous step.
    - `AttributeError`: Check if the object is None or if the attribute name changed.
    - `Google API Error`: Check `.env` and `credentials.json`.
    - `Logic Failure`: If the output says "Done" but the actual result is wrong (e.g., file not found in a search), check the query builder logic.

## 3. Auto-Fixer
- **Targeted Patching:** Use `replace` to fix the specific line.
- **Check Imports:** If adding a new class/function, ensure imports are added.
- **Safety Check:** Ensure the fix doesn't break other parts of the same file.
- **Side Effects:** If you change a function signature, search for all callers in the codebase.

## 4. Retry Manager
- **Count:** Maintain an integer `retry_count` for each command.
- **Reset:** Reset count when moving to a *new* command.
- **Limit:** Max 5 retries.
- **Heuristic:** If the error message is the EXACT same after a fix, your fix was incorrect. Try a different approach or dig deeper into the logs.

## 5. Regression Runner
- If you modified a file that is used by a *previously passed* test command, re-run that previous command immediately.
- Only proceed if the previous test STILL passes.

## 6. Verification Layer
- **Exit Code:** Must be 0.
- **Output Keywords:** Look for "Success", "Completed", or the specific object ID (e.g., File ID, Message ID).
- **Post-run Probe:** If the command was to create a file, use a `ls` or `gws_cli.py` query to verify its existence if possible.

## 7. Reporting Template
```markdown
| Command | Status | Retries | Fix Applied |
|---------|--------|---------|-------------|
| [cmd1] | PASS | 0 | None |
| [cmd2] | PASS | 2 | Fixed typo in drive_query_builder.py |
```
Final Unit Tests: [PASS/FAIL]
Final Status: [OPERATIONAL/BLOCKED]
```
