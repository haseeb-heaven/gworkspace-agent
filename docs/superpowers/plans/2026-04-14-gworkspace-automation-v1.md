# GWorkspace Placeholders Fix and Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `$last_code_stdout` placeholder and execute a series of automation tasks (Doc/Sheet creation, emailing, and verification).

**Architecture:** Update `PlanExecutor` to correctly populate the legacy context from task outputs. Execute sequential tasks using the `run_workflow` engine.

**Tech Stack:** Python, LangChain, Google Workspace APIs (via gws binary).

---

### Task 1: Fix Placeholder Population in PlanExecutor

**Files:**
- Modify: `src/gws_assistant/execution.py`
- Test: `reproduce_bug.py`

- [ ] **Step 1: Update _update_context_from_result to handle stdout**

Modify `src/gws_assistant/execution.py` around line 185:
```python
    def _update_context_from_result(self, data: dict, context: dict) -> None:
        """Extract known artifact keys from a task result and store in context."""
        # Add this:
        if "stdout" in data:
            context["last_code_stdout"] = data["stdout"]
        if "parsed_value" in data:
            context["last_code_result"] = data["parsed_value"]
            
        if "spreadsheetId" in data:
            # ... existing code
```

- [ ] **Step 2: Verify fix with reproduction script**

Run: `D:\henv\Scripts\python.exe reproduce_bug.py`
Expected: Output showing successful replacement of `$last_code_stdout`.

- [ ] **Step 3: Commit fix**

```bash
git add src/gws_assistant/execution.py
git commit -m "fix: populate last_code_stdout and last_code_result in context"
```

---

### Task 2: Automation Task A - Create Doc and Email with Placeholder

- [ ] **Step 1: Execute Task A via CLI**

Run: `python gws_cli.py --task "Search for 'Top 3 agentic AI frameworks', format them with code, create a Google Doc with results, and email the link and the formatted list to haseebmir.hm@gmail.com"`

- [ ] **Step 2: Log action to Telegram**

```bash
python send_telegram.py "Task A: Executing Doc creation and email with placeholder verification."
```

---

### Task 3: Automation Task B - Create Sheet and Email

- [ ] **Step 1: Execute Task B via CLI**

Run: `python gws_cli.py --task "Create a Google Sheet titled 'Automation Test Sheet', add 'Name' and 'Status' headers, and email the link to haseebmir.hm@gmail.com"`

- [ ] **Step 2: Log action to Telegram**

```bash
python send_telegram.py "Task B: Executing Sheet creation and email notification."
```

---

### Task 4: Automation Task C - Verification via Gmail Fetch

- [ ] **Step 1: Execute Task C via CLI**

Run: `python gws_cli.py --task "Fetch the latest email from haseebmir.hm@gmail.com, check if it contains 'Top 3' or 'Automation Test Sheet', and tell me the result."`

- [ ] **Step 2: Log verification result to Telegram**

```bash
python send_telegram.py "Task C: Verification complete. Checking content of sent emails."
```

---

### Task 5: Final Validation

- [ ] **Step 1: Run all unit tests**

Run: `D:\henv\Scripts\python.exe -m pytest tests/`

- [ ] **Step 2: Log final status to Telegram**

```bash
python send_telegram.py "Automation workflow complete. All tests passed. Placeholder fix verified."
```
