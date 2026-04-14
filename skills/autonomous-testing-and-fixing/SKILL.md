---
name: autonomous-testing-and-fixing
description: Use when an autonomous loop is needed to execute a list of manual test commands (e.g., python gws_cli.py --task "..."), fix code failures, retry until passing, and finally run unit tests to ensure zero regressions.
---

# Autonomous Testing and Fixing

## Overview
This skill implements a robust, autonomous "Fix-and-Retry" loop for a list of CLI-based test tasks. It ensures each task passes before moving to the next, fixes code bugs discovered during testing, and verifies the entire system with unit tests.

## Workflow

### 1. Initialization
- **Parse Input:** Identify all commands from the user prompt (typically `python gws_cli.py --task "..."`).
- **Store Sequence:** Maintain the original order of commands.
- **Initialize Tracker:** Prepare to log commands, statuses, errors, fixes, and retry counts.

### 2. Sequential Execution Loop
For each command in the list:
- **Execute:** Run the command using `run_shell_command`.
- **Detect Failure:** Check for non-zero exit codes or keywords like "Error", "Exception", "Traceback", or logical failures in output.
- **Analyze:** If failed, read the output/logs and relevant code to identify the root cause.
- **Fix:** Patch the relevant code path using `replace` or `write_file`. **Always** search for related tests or side effects.
- **Rerun:** Execute the command again.
- **Retry Strategy:** Bounded retries (default 5). If it still fails after 5 attempts, check for external blockers.
- **Regression Check:** If shared logic was modified, rerun any previously successful commands in the current list.

### 3. Final Validation
- **Unit Tests:** After all manual commands pass, run the project's unit test suite (e.g., `pytest`).
- **Fix Regressions:** If unit tests fail, fix them using the same Fix-and-Retry loop.

### 4. Reporting
Generate a structured report at the end:
- **Command:** The executed command.
- **Status:** PASS/FAIL/BLOCKED.
- **Error Found:** Summary of the failure.
- **Fix Applied:** Brief description of the patch.
- **Retry Count:** Number of attempts.
- **Final Unit Test Result:** PASS/FAIL.
- **Final Status:** OPERATIONAL / BLOCKED.

## Behavior Rules
- **No Parallelism:** Commands MUST run sequentially to prevent state collisions.
- **Zero Skipping:** Never proceed to the next command until the current one passes or is definitively blocked by external factors.
- **External Blockers:** Only stop if missing credentials, revoked API access, or missing user resources.
- **Minimal Fixes:** Prioritize surgical fixes over broad refactors.
- **Autonomous Mode:** Do not ask for confirmation for each fix; the user expects you to handle the entire lifecycle.

## Common Failures & Fixes
- **ImportError:** Check `sys.path` or missing `__init__.py`.
- **PermissionError:** Check file permissions or if a file is open.
- **API Error:** Verify `.env` credentials or rate limits.
- **Logic Error:** Trace the data flow and add logging if necessary to find the state mismatch.
